import dataclasses
import logging
import threading
from concurrent.futures import Future
from contextlib import ExitStack, contextmanager
from datetime import datetime
from queue import Empty, Queue
from time import time
from typing import Dict, Generator, List, Optional, Union, cast
from unittest import mock

from google.api_core.exceptions import DeadlineExceeded
from google.auth import default as google_auth_default
from google.auth import environment_vars as google_env_vars
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.subscriber.message import Message as SubscriberMessage
from google.cloud.pubsub_v1.subscriber.scheduler import Scheduler
from google.cloud.pubsub_v1.types import FlowControl, PubsubMessage, ReceivedMessage
from google.protobuf.timestamp_pb2 import Timestamp

from hedwig.backends.base import HedwigConsumerBaseBackend, HedwigPublisherBaseBackend
from hedwig.backends.utils import override_env
from hedwig.conf import settings
from hedwig.models import Message
from hedwig.utils import log

# the default visibility timeout
# ideally find by calling PubSub REST API
DEFAULT_VISIBILITY_TIMEOUT_S = 20


@contextmanager
def _seed_credentials() -> Generator[None, None, None]:
    """
    Seed environment with explicitly set credentials. Normally we'd stay away from mucking with environment vars,
    however the logic to decode `GOOGLE_APPLICATION_CREDENTIALS` isn't simple, so we let Google libraries handle it.
    """
    with ExitStack() as stack:
        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            stack.enter_context(override_env(google_env_vars.CREDENTIALS, settings.GOOGLE_APPLICATION_CREDENTIALS))

        if settings.GOOGLE_CLOUD_PROJECT:
            stack.enter_context(override_env(google_env_vars.PROJECT, settings.GOOGLE_CLOUD_PROJECT))

        yield


def _auto_discover_project() -> None:
    """
    Auto discover Google project id from credentials. If project id is explicitly set, just use that.
    """
    if not settings.GOOGLE_CLOUD_PROJECT:
        # discover project from credentials
        # there's no way to get this from the Client objects, so we reload the credentials
        _, project = google_auth_default()
        assert project, "couldn't discover project"
        setattr(settings, 'GOOGLE_CLOUD_PROJECT', project)


def get_google_cloud_project() -> str:
    if not settings.GOOGLE_CLOUD_PROJECT:
        with _seed_credentials():
            _auto_discover_project()
    return settings.GOOGLE_CLOUD_PROJECT


@dataclasses.dataclass(frozen=True)
class GoogleMetadata:
    """
    Google Pub/Sub specific metadata for a Message
    """

    ack_id: str
    """
    The ID used to ack the message
    """

    subscription_path: str
    """
    Path of the Pub/Sub subscription from which this message was pulled
    """

    publish_time: datetime
    """
    Time this message was originally published to Pub/Sub
    """

    delivery_attempt: int
    """
    The delivery attempt counter received from Pub/Sub.
    The first delivery of a given message will have this value as 1. The value
    is calculated as best effort and is approximate.
    """


class GooglePubSubAsyncPublisherBackend(HedwigPublisherBaseBackend):
    def __init__(self) -> None:
        self._publisher = None

    @property
    def publisher(self):
        if self._publisher is None:
            with _seed_credentials():
                self._publisher = pubsub_v1.PublisherClient(batch_settings=settings.HEDWIG_PUBLISHER_GCP_BATCH_SETTINGS)
        return self._publisher

    def publish_to_topic(self, topic_path: str, data: bytes, attrs: Dict[str, str]) -> Union[str, Future]:
        """
        Publishes to a Google Pub/Sub topic and returns a future that represents the publish API call. These API calls
        are batched for better performance.

        Note: despite the signature this doesn't return an actual instance of Future class, but an object that conforms
        to Future class. There's no generic type to represent future objects though.
        """
        attrs = dict((str(key), str(value)) for key, value in attrs.items())
        return self.publisher.publish(topic_path, data=data, **attrs)

    def _get_topic_path(self, message: Message) -> str:
        topic = self.topic(message)
        if isinstance(topic, tuple):
            topic, project = topic
        else:
            project = get_google_cloud_project()
        return self.publisher.topic_path(project, f'hedwig-{topic}')

    def _mock_queue_message(self, message: Message) -> "MessageWrapper":
        payload, attributes = message.serialize()
        # Pub/Sub requires bytes
        if isinstance(payload, str):
            payload = payload.encode('utf8')
            attributes['hedwig_encoding'] = 'utf8'
        publish_time = Timestamp()
        publish_time.GetCurrentTime()
        pubsub_message = PubsubMessage(
            data=payload,
            attributes=attributes,
            message_id=str(int(time() * 1000)),
            publish_time=publish_time,
        )
        # SubscriberMessage requires raw proto class, not proto-plus
        subscriber_message = SubscriberMessage(PubsubMessage.pb(pubsub_message), 'test-receipt', 1, mock.MagicMock())
        gcp_message = MessageWrapper(subscriber_message, 'test-subscription')
        return gcp_message

    def _publish(self, message: Message, payload: Union[str, bytes], attributes: Dict[str, str]) -> Union[str, Future]:
        topic_path = self._get_topic_path(message)
        # Pub/Sub requires bytes
        if isinstance(payload, str):
            payload = payload.encode('utf8')
            attributes['hedwig_encoding'] = 'utf8'
        return self.publish_to_topic(topic_path, payload, attributes)


class GooglePubSubPublisherBackend(GooglePubSubAsyncPublisherBackend):
    def publish_to_topic(self, topic_path: str, data: bytes, attrs: Dict[str, str]) -> Union[str, Future]:
        return cast(Future, super().publish_to_topic(topic_path, data, attrs)).result()


class MessageWrapper:
    def __init__(self, message: SubscriberMessage, subscription_path: str):
        self._message = message
        self._subscription_path = subscription_path

    @property
    def message(self) -> SubscriberMessage:
        return self._message

    @property
    def subscription_path(self) -> str:
        return self._subscription_path


class PubSubMessageScheduler(Scheduler):
    """
    A scheduler to use with streaming pull that simply queues all messages for the main thread to pick them up.
    """

    def __init__(self, work_queue: Queue, subscription_path: str):
        self._queue: Queue = Queue()
        self._work_queue: Queue = work_queue
        self._subscription_path: str = subscription_path

    @property
    def queue(self) -> Queue:
        """Queue: A thread-safe queue used for communication between callbacks
        and the scheduling thread."""
        return self._queue

    def schedule(self, callback, message: SubscriberMessage, *args, **kwargs) -> None:
        # callback is unused since we never set it in pull_messages
        self._work_queue.put(MessageWrapper(message, self._subscription_path))

    def shutdown(self, await_msg_callbacks=False) -> None:
        """Shuts down the scheduler and immediately end all pending callbacks."""
        # ideally we'd nack the messages in work queue, but that might take some time to finish.
        # instead, it's faster to actually process all the messages


class GooglePubSubConsumerBackend(HedwigConsumerBaseBackend):
    def __init__(self, dlq=False) -> None:
        super().__init__()
        self._subscriber: pubsub_v1.SubscriberClient = None
        self._publisher: pubsub_v1.PublisherClient = None

        if not settings.HEDWIG_SYNC:
            cloud_project = get_google_cloud_project()

            self._subscription_paths: List[str] = []
            if dlq:
                self._subscription_paths = [
                    pubsub_v1.SubscriberClient.subscription_path(cloud_project, f'hedwig-{settings.HEDWIG_QUEUE}-dlq')
                ]
            else:
                self._subscription_paths = []
                for subscription in settings.HEDWIG_SUBSCRIPTIONS:
                    # all subscriptions live in an app's project, but cross-project subscriptions are named differently
                    if isinstance(subscription, str):
                        subscription_name = f'hedwig-{settings.HEDWIG_QUEUE}-{subscription}'
                    else:
                        subscription_name = f'hedwig-{settings.HEDWIG_QUEUE}-{subscription[1]}-{subscription[0]}'
                    self._subscription_paths.append(
                        pubsub_v1.SubscriberClient.subscription_path(cloud_project, subscription_name)
                    )
                # main queue for DLQ re-queued messages
                self._subscription_paths.append(
                    pubsub_v1.SubscriberClient.subscription_path(cloud_project, f'hedwig-{settings.HEDWIG_QUEUE}')
                )
            self._dlq_topic_path: str = pubsub_v1.PublisherClient.topic_path(
                cloud_project, f'hedwig-{settings.HEDWIG_QUEUE}-dlq'
            )

    @property
    def subscriber(self):
        if self._subscriber is None:
            with _seed_credentials():
                self._subscriber = pubsub_v1.SubscriberClient()
        return self._subscriber

    @property
    def publisher(self):
        if self._publisher is None:
            with _seed_credentials():
                self._publisher = pubsub_v1.PublisherClient()
        return self._publisher

    def pull_messages(
        self,
        num_messages: int = 10,
        visibility_timeout: Optional[int] = None,
        shutdown_event: Optional[threading.Event] = None,
    ) -> Union[Generator, List]:
        """
        Pulls messages from PubSub subscriptions, using streaming pull, limiting to num_messages messages at a time
        """
        assert self._subscription_paths, "no subscriptions path: ensure HEDWIG_SUBSCRIPTIONS is set"

        if not shutdown_event:
            shutdown_event = threading.Event()  # pragma: no cover

        work_queue: Queue = Queue()
        futures: List[Future] = []
        flow_control: FlowControl = FlowControl(
            max_messages=num_messages,
            max_duration_per_lease_extension=visibility_timeout or DEFAULT_VISIBILITY_TIMEOUT_S,
        )

        for subscription_path in self._subscription_paths:
            # need a separate scheduler per subscription since the queue is tied to subscription path
            scheduler: PubSubMessageScheduler = PubSubMessageScheduler(work_queue, subscription_path)
            futures.append(
                self.subscriber.subscribe(
                    subscription_path, callback=None, flow_control=flow_control, scheduler=scheduler
                )
            )

        while not shutdown_event.is_set():
            try:
                message = work_queue.get(timeout=1)
                yield message
            except Empty:
                pass

        for future in futures:
            future.cancel()

        # drain the queue
        try:
            while True:
                yield work_queue.get(block=False)
        except Empty:
            pass

    def process_message(self, queue_message: MessageWrapper) -> None:
        # body is always bytes
        message_payload = queue_message.message.data
        attributes = queue_message.message.attributes
        if attributes.get("hedwig_encoding") == "utf8":
            message_payload = message_payload.decode('utf8')
        self.message_handler(
            message_payload,
            attributes,
            GoogleMetadata(
                queue_message.message.ack_id,
                queue_message.subscription_path,
                queue_message.message.publish_time,
                queue_message.message.delivery_attempt,
            ),
        )

    def ack_message(self, queue_message: MessageWrapper) -> None:
        queue_message.message.ack()

    def nack_message(self, queue_message: MessageWrapper) -> None:
        log(__name__, logging.INFO, "nacking message")
        queue_message.message.nack()

    @staticmethod
    def pre_process_hook_kwargs(queue_message: MessageWrapper) -> dict:
        return {'google_pubsub_message': queue_message.message}

    @staticmethod
    def post_process_hook_kwargs(queue_message: MessageWrapper) -> dict:
        return {'google_pubsub_message': queue_message.message}

    def extend_visibility_timeout(self, visibility_timeout_s: int, metadata: GoogleMetadata) -> None:
        """
        Extends visibility timeout of a message on a given priority queue for long running tasks.
        """
        if visibility_timeout_s < 0 or visibility_timeout_s > 600:
            raise ValueError("Invalid visibility_timeout_s")
        self.subscriber.modify_ack_deadline(
            subscription=metadata.subscription_path,
            ack_ids=[metadata.ack_id],
            ack_deadline_seconds=visibility_timeout_s,
        )

    def requeue_dead_letter(self, num_messages: int = 10, visibility_timeout: Optional[int] = None) -> None:
        """
        Re-queues everything in the Hedwig DLQ back into the Hedwig queue.

        :param num_messages: Maximum number of messages to fetch in one call. Defaults to 10.
        :param visibility_timeout: The number of seconds the message should remain invisible to other queue readers.
        Defaults to None, which is queue default
        """
        topic_path = pubsub_v1.PublisherClient.topic_path(get_google_cloud_project(), f'hedwig-{settings.HEDWIG_QUEUE}')
        assert len(self._subscription_paths) == 1, "multiple subscriptions found"
        subscription_path = self._subscription_paths[0]

        log(__name__, logging.INFO, "Re-queueing messages from {} to {}".format(subscription_path, topic_path))
        while True:
            try:
                queue_messages: List[ReceivedMessage] = self.subscriber.pull(
                    subscription=subscription_path,
                    max_messages=num_messages,
                    retry=None,
                    timeout=settings.GOOGLE_PUBSUB_READ_TIMEOUT_S,
                ).received_messages
            except DeadlineExceeded:
                break

            if not queue_messages:
                break

            log(__name__, logging.INFO, "got {} messages from dlq".format(len(queue_messages)))
            for queue_message in queue_messages:
                try:
                    if visibility_timeout:
                        self.subscriber.modify_ack_deadline(
                            subscription=subscription_path,
                            ack_ids=[queue_message.ack_id],
                            ack_deadline_seconds=visibility_timeout,
                        )

                    future = self.publisher.publish(
                        topic_path, data=queue_message.message.data, **queue_message.message.attributes
                    )
                    # wait for success
                    future.result()
                    log(
                        __name__,
                        logging.DEBUG,
                        'Re-queued message from DLQ {} to {}'.format(subscription_path, topic_path),
                        extra={'message_id': queue_message.message.message_id},
                    )

                    self.subscriber.acknowledge(subscription=subscription_path, ack_ids=[queue_message.ack_id])
                except Exception:
                    log(
                        __name__,
                        logging.ERROR,
                        'Exception in requeue message from {} to {}'.format(subscription_path, topic_path),
                        exc_info=True,
                    )

            log(__name__, logging.INFO, "Re-queued {} messages".format(len(queue_messages)))
