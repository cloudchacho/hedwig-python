import base64
import dataclasses
import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from time import time
from typing import cast, Optional, Generator, List, Union, Dict, Iterator
from unittest import mock

import boto3
import funcy
from botocore.config import Config
from retrying import retry

from hedwig.backends.base import HedwigConsumerBaseBackend, HedwigPublisherBaseBackend
from hedwig.backends.exceptions import PartialFailure
from hedwig.conf import settings
from hedwig.models import Message
from hedwig.utils import log


@dataclasses.dataclass(frozen=True)
class AWSMetadata:
    """
    AWS specific metadata for a Message
    """

    receipt: str
    """
    AWS receipt identifier
    """

    first_receive_time: datetime
    """
    The time the message was first received from the queue. The value
    is calculated as best effort and is approximate.
    """

    sent_time: datetime
    """
    Time this message was originally sent to AWS
    """

    receive_count: int
    """
    The receive count received from SQS.
    The first delivery of a given message will have this value as 1. The value
    is calculated as best effort and is approximate.
    """


class AWSSNSPublisherBackend(HedwigPublisherBaseBackend):
    def __init__(self):
        self._sns_client = None

    @property
    def sns_client(self):
        if self._sns_client is None:
            config = Config(connect_timeout=settings.AWS_CONNECT_TIMEOUT_S, read_timeout=settings.AWS_READ_TIMEOUT_S)
            self._sns_client = boto3.client(
                'sns',
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY,
                aws_secret_access_key=settings.AWS_SECRET_KEY,
                aws_session_token=settings.AWS_SESSION_TOKEN,
                endpoint_url=settings.AWS_ENDPOINT_SNS,
                config=config,
            )
        return self._sns_client

    @classmethod
    def _get_sns_topic(cls, message: Message) -> str:
        topic = cls.topic(message)
        if isinstance(topic, tuple):
            topic, account_id = topic
        else:
            account_id = settings.AWS_ACCOUNT_ID
        return f'arn:aws:sns:{settings.AWS_REGION}:{account_id}:hedwig-{topic}'

    @retry(stop_max_attempt_number=3, stop_max_delay=3000)
    def _publish_over_sns(self, topic: str, message_payload: str, attributes: Dict[str, str]) -> str:
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sns.html#SNS.Topic.publish
        message_attributes = {str(k): {'DataType': 'String', 'StringValue': str(v)} for k, v in attributes.items()}
        response = self.sns_client.publish(
            TopicArn=topic, Message=message_payload, MessageAttributes=message_attributes
        )
        return response['MessageId']

    def _mock_queue_message(self, message: Message) -> mock.Mock:
        sqs_message = mock.Mock()
        payload, attributes = message.serialize()
        # SQS requires UTF-8 encoded string
        if isinstance(payload, bytes):
            payload = base64.encodebytes(payload).decode()
            attributes['hedwig_encoding'] = 'base64'
        sqs_message.body = payload
        sqs_message.message_attributes = {
            k: {'DataType': 'String', 'StringValue': str(v)} for k, v in attributes.items()
        }
        sqs_message.attributes = {
            'ApproximateReceiveCount': 1,
            'SentTimestamp': int(time() * 1000),
            'ApproximateFirstReceiveTimestamp': int(time() * 1000),
        }
        sqs_message.receipt_handle = 'test-receipt'
        return sqs_message

    def _publish(self, message: Message, payload: Union[str, bytes], attributes: Dict[str, str]) -> str:
        topic = self._get_sns_topic(message)
        # SNS requires UTF-8 encoded string
        if isinstance(payload, bytes):
            payload = base64.encodebytes(payload).decode()
            attributes['hedwig_encoding'] = 'base64'
        return self._publish_over_sns(topic, payload, attributes)


class AWSSQSConsumerBackend(HedwigConsumerBaseBackend):
    WAIT_TIME_SECONDS = 20

    def __init__(self, dlq=False):
        super().__init__()
        self._sqs_resource = None
        self._sqs_client = None
        self.queue_name = f'HEDWIG-{settings.HEDWIG_QUEUE}{"-DLQ" if dlq else ""}'

    @property
    def sqs_resource(self):
        if self._sqs_resource is None:
            self._sqs_resource = boto3.resource(
                'sqs',
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY,
                aws_secret_access_key=settings.AWS_SECRET_KEY,
                aws_session_token=settings.AWS_SESSION_TOKEN,
                endpoint_url=settings.AWS_ENDPOINT_SQS,
            )
        return self._sqs_resource

    @property
    def sqs_client(self):
        if self._sqs_client is None:
            self._sqs_client = boto3.client(
                'sqs',
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY,
                aws_secret_access_key=settings.AWS_SECRET_KEY,
                aws_session_token=settings.AWS_SESSION_TOKEN,
                endpoint_url=settings.AWS_ENDPOINT_SQS,
            )
        return self._sqs_client

    def _get_queue(self):
        return self.sqs_resource.get_queue_by_name(QueueName=self.queue_name)

    def pull_messages(
        self,
        num_messages: int = 10,
        visibility_timeout: Optional[int] = None,
        shutdown_event: Optional[threading.Event] = None,
    ) -> Union[Generator, List]:
        """

        :param shutdown_event: Unused for this backend
        :param num_messages:
        :param visibility_timeout:
        :return:
        """
        params = {
            'MaxNumberOfMessages': num_messages,
            'WaitTimeSeconds': self.WAIT_TIME_SECONDS,
            'AttributeNames': ['All'],
            'MessageAttributeNames': ['All'],
        }
        if visibility_timeout is not None:
            params['VisibilityTimeout'] = visibility_timeout
        return self._get_queue().receive_messages(**params)

    def process_message(self, queue_message) -> None:
        attributes = {k: o['StringValue'] for k, o in (queue_message.message_attributes or {}).items()}
        # body is always UTF-8 string
        message_payload = queue_message.body
        if attributes.get("hedwig_encoding") == "base64":
            message_payload = base64.decodebytes(message_payload.encode())
        receipt = queue_message.receipt_handle
        self.message_handler(
            message_payload,
            attributes,
            AWSMetadata(
                receipt,
                datetime.fromtimestamp(
                    int(queue_message.attributes['ApproximateFirstReceiveTimestamp']) / 1000, tz=timezone.utc
                ),
                datetime.fromtimestamp(int(queue_message.attributes['SentTimestamp']) / 1000, tz=timezone.utc),
                int(queue_message.attributes['ApproximateReceiveCount']),
            ),
        )

    def ack_message(self, queue_message) -> None:
        queue_message.delete()

    def nack_message(self, queue_message) -> None:
        # let visibility timeout take care of it
        pass

    def extend_visibility_timeout(self, visibility_timeout_s: int, metadata: AWSMetadata) -> None:
        """
        Extends visibility timeout of a message on a given priority queue for long running tasks.
        """
        receipt = metadata.receipt
        queue_url = self.sqs_client.get_queue_url(QueueName=self.queue_name)['QueueUrl']
        self.sqs_client.change_message_visibility(
            QueueUrl=queue_url, ReceiptHandle=receipt, VisibilityTimeout=visibility_timeout_s
        )

    def requeue_dead_letter(self, num_messages: int = 10, visibility_timeout: Optional[int] = None) -> None:
        """
        Re-queues everything in the Hedwig DLQ back into the Hedwig queue.

        :param num_messages: Maximum number of messages to fetch in one SQS call. Defaults to 10.
        :param visibility_timeout: The number of seconds the message should remain invisible to other queue readers.
        Defaults to None, which is queue default
        """
        sqs_queue = self.sqs_resource.get_queue_by_name(QueueName=f'HEDWIG-{settings.HEDWIG_QUEUE}')
        dead_letter_queue = self._get_queue()

        log(__name__, logging.INFO, "Re-queueing messages from {} to {}".format(dead_letter_queue.url, sqs_queue.url))
        while True:
            queue_messages = self.pull_messages(num_messages=num_messages, visibility_timeout=visibility_timeout)
            queue_messages = cast(list, queue_messages)

            if not queue_messages:
                break

            log(__name__, logging.INFO, "got {} messages from dlq".format(len(queue_messages)))

            result = sqs_queue.send_messages(
                Entries=[
                    funcy.merge(
                        {'Id': queue_message.message_id, 'MessageBody': queue_message.body},
                        {'MessageAttributes': queue_message.message_attributes}
                        if queue_message.message_attributes
                        else {},
                    )
                    for queue_message in queue_messages
                ]
            )
            if result.get('Failed'):
                raise PartialFailure(result)

            dead_letter_queue.delete_messages(
                Entries=[
                    {'Id': message.message_id, 'ReceiptHandle': message.receipt_handle} for message in queue_messages
                ]
            )

            log(__name__, logging.INFO, "Re-queued {} messages".format(len(queue_messages)))

    @staticmethod
    def pre_process_hook_kwargs(queue_message) -> dict:
        return {'sqs_queue_message': queue_message}

    @staticmethod
    def post_process_hook_kwargs(queue_message) -> dict:
        return {'sqs_queue_message': queue_message}


class AWSSNSConsumerBackend(HedwigConsumerBaseBackend):
    def requeue_dead_letter(self, num_messages: int = 10, visibility_timeout: Optional[int] = None) -> None:
        raise RuntimeError("invalid operation for backend")  # pragma: no cover

    def pull_messages(
        self,
        num_messages: int = 10,
        visibility_timeout: Optional[int] = None,
        shutdown_event: Optional[threading.Event] = None,
    ) -> Union[Generator, List]:
        raise RuntimeError("invalid operation for backend")  # pragma: no cover

    def ack_message(self, queue_message) -> None:
        raise RuntimeError("invalid operation for backend")  # pragma: no cover

    def nack_message(self, queue_message) -> None:
        raise RuntimeError("invalid operation for backend")  # pragma: no cover

    def extend_visibility_timeout(self, visibility_timeout_s: int, metadata) -> None:
        raise RuntimeError("invalid operation for backend")  # pragma: no cover

    @contextmanager
    def _maybe_instrument(self, **kwargs) -> Iterator:
        try:
            import hedwig.instrumentation

            with hedwig.instrumentation.on_receive(**kwargs) as span:
                yield span
        except ImportError:
            yield None

    def process_messages(self, lambda_event):
        for record in lambda_event['Records']:
            with self._maybe_instrument(sns_record=record):
                self.process_message(record)

    def process_message(self, queue_message) -> None:
        settings.HEDWIG_PRE_PROCESS_HOOK(sns_record=queue_message)
        message_payload = queue_message['Sns']['Message']
        attributes = {k: o['Value'] for k, o in queue_message['Sns']['MessageAttributes'].items()}
        if attributes.get("hedwig_encoding") == "base64":
            message_payload = base64.decodebytes(message_payload.encode()).decode()
        self.message_handler(message_payload, attributes, None)
        settings.HEDWIG_POST_PROCESS_HOOK(sns_record=queue_message)
