import json
import logging
import typing
from collections import Counter

import mock
from google.api_core.exceptions import DeadlineExceeded
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.proto.pubsub_pb2 import ReceivedMessage
from retrying import retry

from hedwig.backends.base import HedwigPublisherBaseBackend, HedwigConsumerBaseBackend
from hedwig.backends.import_utils import import_class
from hedwig.conf import settings
from hedwig.models import Message


logger = logging.getLogger(__name__)


# TODO move to dataclasses in py3.7
class GoogleMetadata:
    def __init__(self, ack_id):
        self._ack_id = ack_id

    @property
    def ack_id(self):
        return self._ack_id

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, GoogleMetadata):
            return False
        return self.ack_id == o.ack_id

    def __ne__(self, o: object) -> bool:
        return not self.__eq__(o)

    def __str__(self) -> str:
        return repr(self)

    def __repr__(self) -> str:
        return f'GoogleMetadata(ack_id={self.ack_id})'

    def __hash__(self) -> int:
        return hash((self.ack_id,))


class GooglePubSubPublisherBackend(HedwigPublisherBaseBackend):
    def __init__(self) -> None:
        self.publisher = pubsub_v1.PublisherClient.from_service_account_file(settings.GOOGLE_APPLICATION_CREDENTIALS)

    @retry(stop_max_attempt_number=3, stop_max_delay=3000)
    def publish_to_topic(self, topic_path: str, data: bytes, attrs: typing.Optional[dict] = None) -> str:
        attrs = attrs or {}
        attrs = dict((str(key), str(value)) for key, value in attrs.items())
        return self.publisher.publish(topic_path, data=data, **attrs).result()

    def _get_topic_path(self, message: Message) -> str:
        return self.publisher.topic_path(settings.GOOGLE_PUBSUB_PROJECT_ID, f'hedwig-{message.topic}')

    def _mock_queue_message(self, message: Message) -> mock.Mock:
        gcp_message = mock.Mock()
        gcp_message.message = mock.Mock()
        gcp_message.message.data = json.dumps(message.as_dict()).encode('utf8')
        gcp_message.ack_id = 'test-receipt'
        return gcp_message

    def _publish(self, message: Message, payload: str, headers: typing.Optional[typing.Mapping] = None) -> str:
        topic_path = self._get_topic_path(message)
        return self.publish_to_topic(topic_path, payload.encode('utf8'), headers)


class GooglePubSubConsumerBackend(HedwigConsumerBaseBackend):
    def __init__(self, dlq=False) -> None:
        self.subscriber = pubsub_v1.SubscriberClient.from_service_account_file(settings.GOOGLE_APPLICATION_CREDENTIALS)
        self._publisher = pubsub_v1.PublisherClient.from_service_account_file(settings.GOOGLE_APPLICATION_CREDENTIALS)
        self.message_retry_state: typing.Optional[MessageRetryStateBackend] = None
        self._subscription_path: str = pubsub_v1.SubscriberClient.subscription_path(
            settings.GOOGLE_PUBSUB_PROJECT_ID, f'hedwig-{settings.HEDWIG_QUEUE}{"-dlq" if dlq else ""}'
        )
        self._dlq_topic_path: str = pubsub_v1.PublisherClient.topic_path(
            settings.GOOGLE_PUBSUB_PROJECT_ID, f'hedwig-{settings.HEDWIG_QUEUE}-dlq'
        )
        if settings.HEDWIG_GOOGLE_MESSAGE_RETRY_STATE_BACKEND:
            message_retry_state_cls = import_class(settings.HEDWIG_GOOGLE_MESSAGE_RETRY_STATE_BACKEND)
            self.message_retry_state = message_retry_state_cls()

    def pull_messages(self, num_messages: int = 1, visibility_timeout: int = None) -> typing.List:
        try:
            received_messages = self.subscriber.pull(
                self._subscription_path, num_messages, retry=None, timeout=settings.GOOGLE_PUBSUB_READ_TIMEOUT_S
            ).received_messages
            return received_messages
        except DeadlineExceeded:
            logger.debug(f"Pulling deadline exceeded subscription={self._subscription_path}")
            return []

    def process_message(self, queue_message: ReceivedMessage) -> None:
        try:
            self.message_handler(queue_message.message.data.decode(), GoogleMetadata(queue_message.ack_id))
        except Exception:
            if self._can_reprocess_message(queue_message):
                raise

    def delete_message(self, queue_message: ReceivedMessage) -> None:
        self.subscriber.acknowledge(self._subscription_path, [queue_message.ack_id])

    @staticmethod
    def pre_process_hook_kwargs(queue_message: ReceivedMessage) -> dict:
        return {'google_pubsub_message': queue_message}

    @staticmethod
    def post_process_hook_kwargs(queue_message: ReceivedMessage) -> dict:
        return {'google_pubsub_message': queue_message}

    def extend_visibility_timeout(self, visibility_timeout_s: int, metadata: GoogleMetadata) -> None:
        """
        Extends visibility timeout of a message on a given priority queue for long running tasks.
        """
        if visibility_timeout_s < 0 or visibility_timeout_s > 600:
            raise ValueError("Invalid visibility_timeout_s")
        self.subscriber.modify_ack_deadline(self._subscription_path, [metadata.ack_id], visibility_timeout_s)

    def requeue_dead_letter(self, num_messages: int = 10, visibility_timeout: int = None) -> None:
        """
        Re-queues everything in the Hedwig DLQ back into the Hedwig queue.

        :param num_messages: Maximum number of messages to fetch in one call. Defaults to 10.
        :param visibility_timeout: The number of seconds the message should remain invisible to other queue readers.
        Defaults to None, which is queue default
        """
        topic_path = pubsub_v1.PublisherClient.topic_path(
            settings.GOOGLE_PUBSUB_PROJECT_ID, f'hedwig-{settings.HEDWIG_QUEUE}'
        )

        logging.info("Re-queueing messages from {} to {}".format(self._subscription_path, topic_path))
        while True:
            queue_messages = self.pull_messages(num_messages=num_messages, visibility_timeout=visibility_timeout)
            if not queue_messages:
                break

            logging.info("got {} messages from dlq".format(len(queue_messages)))
            for queue_message in queue_messages:
                try:
                    if visibility_timeout:
                        self.subscriber.modify_ack_deadline([queue_message.ack_id], visibility_timeout)

                    self._publisher.publish(topic_path, data=queue_message.message.data, **queue_message.attributes)
                    logger.debug(
                        'Re-queued message from DLQ {} to {}'.format(self._subscription_path, topic_path),
                        extra={'message_id': queue_message.message_id},
                    )

                    self.delete_message(queue_message)
                except Exception:
                    logger.exception(
                        'Exception in requeue message from {} to {}'.format(self._subscription_path, topic_path)
                    )

            logging.info("Re-queued {} messages".format(len(queue_messages)))

    def _can_reprocess_message(self, queue_message: ReceivedMessage) -> bool:
        if not self.message_retry_state:
            return True

        try:
            self.message_retry_state.inc(queue_message.message.message_id, self._subscription_path)
            return True
        except MaxRetriesExceededError:
            self._move_message_to_dlq(queue_message)
        return False

    def _move_message_to_dlq(self, queue_message: ReceivedMessage) -> None:
        self._publisher.publish(self._dlq_topic_path, queue_message.message.data, **queue_message.attributes)
        logger.debug('Sent message to DLQ', extra={'message_id': queue_message.message_id})


class MaxRetriesExceededError(Exception):
    pass


class MessageRetryStateBackend:
    def __init__(self) -> None:
        self.max_tries = settings.HEDWIG_GOOGLE_MESSAGE_MAX_RETRIES

    def inc(self, message_id: str, queue_name: str) -> None:
        raise NotImplementedError

    @staticmethod
    def _get_hash(message_id: str, queue_name: str) -> str:
        return f"{queue_name}-{message_id}"


class MessageRetryStateLocMem(MessageRetryStateBackend):
    DB: typing.Counter = Counter()

    def inc(self, message_id: str, queue_name: str) -> None:
        key = self._get_hash(message_id, queue_name)
        self.DB[key] += 1
        if self.DB[key] >= self.max_tries:
            raise MaxRetriesExceededError


class MessageRetryStateRedis(MessageRetryStateBackend):
    def __init__(self) -> None:
        import redis

        super().__init__()
        self.client = redis.from_url(settings.GOOGLE_MESSAGE_RETRY_STATE_REDIS_URL)

    def inc(self, message_id: str, queue_name: str) -> None:
        key = self._get_hash(message_id, queue_name)
        value = self.client.incr(key)
        if value >= self.max_tries:
            self.client.expire(key, 0)
            raise MaxRetriesExceededError
