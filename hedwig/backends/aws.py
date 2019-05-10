import json
import logging
import typing
from unittest import mock

import boto3
import funcy
from botocore.config import Config
from retrying import retry

from hedwig.backends.base import HedwigConsumerBaseBackend, HedwigPublisherBaseBackend
from hedwig.backends.exceptions import PartialFailure
from hedwig.conf import settings
from hedwig.models import Message


logger = logging.getLogger(__name__)


class AWSMetadata:
    def __init__(self, receipt):
        self._receipt = receipt

    @property
    def receipt(self):
        return self._receipt

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, AWSMetadata):
            return False
        return self._receipt == o._receipt

    def __ne__(self, o: object) -> bool:
        return not self.__eq__(o)

    def __str__(self) -> str:
        return repr(self)

    def __repr__(self) -> str:
        return f'GoogleMetadata(ack_id={self._receipt})'

    def __hash__(self) -> int:
        return hash((self._receipt,))


class AWSSNSPublisherBackend(HedwigPublisherBaseBackend):
    def __init__(self):
        config = Config(connect_timeout=settings.AWS_CONNECT_TIMEOUT_S, read_timeout=settings.AWS_READ_TIMEOUT_S)
        self.sns_client = boto3.client(
            'sns',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY,
            aws_secret_access_key=settings.AWS_SECRET_KEY,
            aws_session_token=settings.AWS_SESSION_TOKEN,
            endpoint_url=settings.AWS_ENDPOINT_SNS,
            config=config,
        )

    @staticmethod
    def _get_sns_topic(message: Message) -> str:
        return f'arn:aws:sns:{settings.AWS_REGION}:{settings.AWS_ACCOUNT_ID}:hedwig-{message.topic}'

    @retry(stop_max_attempt_number=3, stop_max_delay=3000)
    def _publish_over_sns(self, topic: str, message_json: str, message_attributes: dict) -> str:
        # transform (http://boto.cloudhackers.com/en/latest/ref/sns.html#boto.sns.SNSConnection.publish)
        message_attributes = {k: {'DataType': 'String', 'StringValue': str(v)} for k, v in message_attributes.items()}
        response = self.sns_client.publish(TopicArn=topic, Message=message_json, MessageAttributes=message_attributes)
        return response['PublishResponse']['PublishResult']['MessageId']

    def _mock_queue_message(self, message: Message) -> mock.Mock:
        sqs_message = mock.Mock()
        sqs_message.body = json.dumps(message.as_dict())
        sqs_message.receipt_handle = 'test-receipt'
        return sqs_message

    def _publish(self, message: Message, payload: str, headers: typing.Optional[typing.Mapping] = None) -> str:
        topic = self._get_sns_topic(message)
        return self._publish_over_sns(topic, payload, headers)


class AWSSQSConsumerBackend(HedwigConsumerBaseBackend):
    WAIT_TIME_SECONDS = 20

    def __init__(self, dlq=False):
        self.sqs_resource = boto3.resource(
            'sqs',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY,
            aws_secret_access_key=settings.AWS_SECRET_KEY,
            aws_session_token=settings.AWS_SESSION_TOKEN,
            endpoint_url=settings.AWS_ENDPOINT_SQS,
        )
        self.sqs_client = boto3.client(
            'sqs',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY,
            aws_secret_access_key=settings.AWS_SECRET_KEY,
            aws_session_token=settings.AWS_SESSION_TOKEN,
            endpoint_url=settings.AWS_ENDPOINT_SQS,
        )
        self.queue_name = f'HEDWIG-{settings.HEDWIG_QUEUE}{"-DLQ" if dlq else ""}'

    def _get_queue(self):
        return self.sqs_resource.get_queue_by_name(QueueName=self.queue_name)

    def pull_messages(self, num_messages: int = 1, visibility_timeout: int = None) -> typing.List:
        params = {
            'MaxNumberOfMessages': num_messages,
            'WaitTimeSeconds': self.WAIT_TIME_SECONDS,
            'MessageAttributeNames': ['All'],
        }
        if visibility_timeout is not None:
            params['VisibilityTimeout'] = visibility_timeout
        return self._get_queue().receive_messages(**params)

    def process_message(self, queue_message) -> None:
        message_json = queue_message.body
        receipt = queue_message.receipt_handle
        self.message_handler(message_json, AWSMetadata(receipt))

    def delete_message(self, queue_message) -> None:
        queue_message.delete()

    def extend_visibility_timeout(self, visibility_timeout_s: int, metadata: AWSMetadata) -> None:
        """
        Extends visibility timeout of a message on a given priority queue for long running tasks.
        """
        receipt = metadata.receipt
        queue_url = self.sqs_client.get_queue_url(QueueName=self.queue_name)['QueueUrl']
        self.sqs_client.change_message_visibility(
            QueueUrl=queue_url, ReceiptHandle=receipt, VisibilityTimeout=visibility_timeout_s
        )

    def requeue_dead_letter(self, num_messages: int = 10, visibility_timeout: int = None) -> None:
        """
        Re-queues everything in the Hedwig DLQ back into the Hedwig queue.

        :param num_messages: Maximum number of messages to fetch in one SQS call. Defaults to 10.
        :param visibility_timeout: The number of seconds the message should remain invisible to other queue readers.
        Defaults to None, which is queue default
        """
        sqs_queue = self.sqs_resource.get_queue_by_name(QueueName=f'HEDWIG-{settings.HEDWIG_QUEUE}')
        dead_letter_queue = self._get_queue()

        logging.info("Re-queueing messages from {} to {}".format(dead_letter_queue.url, sqs_queue.url))
        while True:
            queue_messages = self.pull_messages(num_messages=num_messages, visibility_timeout=visibility_timeout)
            if not queue_messages:
                break

            logging.info("got {} messages from dlq".format(len(queue_messages)))

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

            logging.info("Re-queued {} messages".format(len(queue_messages)))

    @staticmethod
    def pre_process_hook_kwargs(queue_message) -> dict:
        return {'sqs_queue_message': queue_message}

    @staticmethod
    def post_process_hook_kwargs(queue_message) -> dict:
        return {'sqs_queue_message': queue_message}


class AWSSNSConsumerBackend(HedwigConsumerBaseBackend):
    def process_message(self, queue_message) -> None:
        settings.HEDWIG_PRE_PROCESS_HOOK(sns_record=queue_message)
        message_json = queue_message['Sns']['Message']
        self.message_handler(message_json, None)
        settings.HEDWIG_POST_PROCESS_HOOK(sns_record=queue_message)
