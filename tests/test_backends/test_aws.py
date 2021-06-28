import base64
import json
import threading
import uuid
from datetime import datetime, timezone
from unittest import mock

import freezegun
import pytest

try:
    from hedwig.backends.aws import AWSMetadata
except ImportError:
    pass
from hedwig.backends.exceptions import PartialFailure
from hedwig.conf import settings as hedwig_settings
from hedwig.exceptions import ValidationError, CallbackNotFound

from tests.models import MessageType
from tests.utils.mock import mock_return_once

aws = pytest.importorskip('hedwig.backends.aws')


class TestSNSPublisher:
    def test__get_sns_topic(self, message_factory):
        sns_publisher = aws.AWSSNSPublisherBackend()
        message = message_factory(msg_type=MessageType.vehicle_created)
        assert (
            sns_publisher._get_sns_topic(message)
            == 'arn:aws:sns:DUMMY_REGION:project-id-or-account-id:hedwig-dev-vehicle-created-v1'
        )

    def test_publish_success(self, mock_boto3, message, use_transport_message_attrs):
        sns_publisher = aws.AWSSNSPublisherBackend()
        queue = mock.MagicMock()
        sns_publisher.sns_client.publish.get_queue_by_name = mock.MagicMock(return_value=queue)

        sns_publisher.publish(message)

        mock_boto3.client.assert_called_once_with(
            'sns',
            region_name=hedwig_settings.AWS_REGION,
            aws_access_key_id=hedwig_settings.AWS_ACCESS_KEY,
            aws_secret_access_key=hedwig_settings.AWS_SECRET_KEY,
            aws_session_token=hedwig_settings.AWS_SESSION_TOKEN,
            endpoint_url=hedwig_settings.AWS_ENDPOINT_SQS,
            config=mock.ANY,
        )
        topic = sns_publisher._get_sns_topic(message)
        data, attrs = message.serialize()
        if not use_transport_message_attrs:
            attrs = message.headers
        if isinstance(data, bytes):
            data = base64.encodebytes(data).decode()
            attrs['hedwig_encoding'] = 'base64'
        sns_publisher.sns_client.publish.assert_called_once_with(
            TopicArn=topic,
            Message=data,
            MessageAttributes={k: {'DataType': 'String', 'StringValue': str(v)} for k, v in attrs.items()},
        )

    @freezegun.freeze_time()
    @mock.patch('tests.handlers._trip_created_handler', autospec=True)
    def test_sync_mode(self, callback_mock, mock_boto3, message, mock_publisher_backend, settings):
        settings.HEDWIG_PUBLISHER_BACKEND = 'hedwig.backends.aws.AWSSNSPublisherBackend'
        settings.HEDWIG_CONSUMER_BACKEND = 'hedwig.backends.aws.AWSSQSConsumerBackend'
        settings.HEDWIG_SYNC = True
        receipt = 'test-receipt'
        sent_time = datetime.now(timezone.utc)
        sent_time = sent_time.replace(microsecond=(sent_time.microsecond // 1000) * 1000)
        first_receive_time = datetime.now(timezone.utc)
        first_receive_time = first_receive_time.replace(microsecond=(first_receive_time.microsecond // 1000) * 1000)
        receive_count = 1

        message.publish()
        callback_mock.assert_called_once_with(
            message.with_provider_metadata(AWSMetadata(receipt, first_receive_time, sent_time, receive_count))
        )

    def test_sync_mode_detects_invalid_callback(self, settings, mock_boto3, message_factory):
        settings.HEDWIG_PUBLISHER_BACKEND = 'hedwig.backends.aws.AWSSNSPublisherBackend'
        settings.HEDWIG_CONSUMER_BACKEND = 'hedwig.backends.aws.AWSSQSConsumerBackend'
        settings.HEDWIG_SYNC = True

        message = message_factory(msg_type=MessageType.vehicle_created)
        with pytest.raises(ValidationError) as exc_info:
            message.publish()
        assert isinstance(exc_info.value.__context__, CallbackNotFound)


pre_process_hook = mock.MagicMock()
post_process_hook = mock.MagicMock()


@pytest.fixture(name='sqs_consumer')
def _sqs_consumer(mock_boto3):
    return aws.AWSSQSConsumerBackend()


@pytest.fixture(name='sns_consumer')
def _sns_consumer(mock_boto3):
    return aws.AWSSNSConsumerBackend()


@pytest.fixture(name='prepost_process_hooks')
def _prepost_process_hooks(settings):
    settings.HEDWIG_PRE_PROCESS_HOOK = 'tests.test_backends.test_aws.pre_process_hook'
    settings.HEDWIG_POST_PROCESS_HOOK = 'tests.test_backends.test_aws.post_process_hook'
    yield
    pre_process_hook.reset_mock()
    post_process_hook.reset_mock()


class TestSQSConsumer:
    def test_client_and_resource_instantiation(self, sqs_consumer, mock_boto3):
        # make sure client and resource are initialized
        sqs_consumer.sqs_client
        sqs_consumer.sqs_resource
        mock_boto3.resource.assert_called_once_with(
            'sqs',
            region_name=hedwig_settings.AWS_REGION,
            aws_access_key_id=hedwig_settings.AWS_ACCESS_KEY,
            aws_secret_access_key=hedwig_settings.AWS_SECRET_KEY,
            aws_session_token=hedwig_settings.AWS_SESSION_TOKEN,
            endpoint_url=hedwig_settings.AWS_ENDPOINT_SQS,
        )
        mock_boto3.client.assert_called_once_with(
            'sqs',
            region_name=hedwig_settings.AWS_REGION,
            aws_access_key_id=hedwig_settings.AWS_ACCESS_KEY,
            aws_secret_access_key=hedwig_settings.AWS_SECRET_KEY,
            aws_session_token=hedwig_settings.AWS_SESSION_TOKEN,
            endpoint_url=hedwig_settings.AWS_ENDPOINT_SQS,
        )

    def test_pull_messages(self, sqs_consumer):
        num_messages = 1
        visibility_timeout = 10
        queue = mock.MagicMock()
        sqs_consumer.sqs_resource.get_queue_by_name = mock.MagicMock(return_value=queue)

        sqs_consumer.pull_messages(num_messages, visibility_timeout)

        sqs_consumer.sqs_resource.get_queue_by_name.assert_called_once_with(QueueName=sqs_consumer.queue_name)
        queue.receive_messages.assert_called_once_with(
            MaxNumberOfMessages=num_messages,
            MessageAttributeNames=['All'],
            AttributeNames=['All'],
            VisibilityTimeout=visibility_timeout,
            WaitTimeSeconds=sqs_consumer.WAIT_TIME_SECONDS,
        )

    def test_extend_visibility_timeout(self, sqs_consumer):
        visibility_timeout_s = 10
        receipt = "receipt"
        sent_time = datetime.now(timezone.utc)
        first_receive_time = datetime.now(timezone.utc)
        receive_count = 1

        sqs_consumer.sqs_client.get_queue_url = mock.MagicMock(return_value={"QueueUrl": "DummyQueueUrl"})

        sqs_consumer.extend_visibility_timeout(
            visibility_timeout_s, AWSMetadata(receipt, first_receive_time, sent_time, receive_count)
        )

        sqs_consumer.sqs_client.get_queue_url.assert_called_once_with(QueueName=sqs_consumer.queue_name)
        sqs_consumer.sqs_client.change_message_visibility.assert_called_once_with(
            QueueUrl='DummyQueueUrl', ReceiptHandle='receipt', VisibilityTimeout=10
        )

    def test_success_requeue_dead_letter(self, sqs_consumer):
        sqs_consumer = aws.AWSSQSConsumerBackend(dlq=True)
        num_messages = 3
        visibility_timeout = 4

        messages = [mock.MagicMock() for _ in range(num_messages)]
        sqs_consumer.pull_messages = mock.MagicMock(side_effect=iter([messages, []]))

        mock_queue, mock_dlq = mock.MagicMock(), mock.MagicMock()
        mock_queue.send_messages.return_value = {'Failed': []}
        sqs_consumer.sqs_resource.get_queue_by_name = mock.MagicMock(side_effect=iter([mock_queue, mock_dlq]))
        mock_dlq.delete_messages.return_value = {'Failed': []}

        sqs_consumer.requeue_dead_letter(num_messages=num_messages, visibility_timeout=visibility_timeout)

        sqs_consumer.sqs_resource.get_queue_by_name.assert_has_calls(
            [
                mock.call(QueueName=f'HEDWIG-{hedwig_settings.HEDWIG_QUEUE}'),
                mock.call(QueueName=sqs_consumer.queue_name),
            ]
        )

        sqs_consumer.pull_messages.assert_has_calls(
            [
                mock.call(num_messages=num_messages, visibility_timeout=visibility_timeout),
                mock.call(num_messages=num_messages, visibility_timeout=visibility_timeout),
            ]
        )
        mock_queue.send_messages.assert_called_once_with(
            Entries=[
                {
                    'Id': queue_message.message_id,
                    'MessageBody': queue_message.body,
                    'MessageAttributes': queue_message.message_attributes,
                }
                for queue_message in messages
            ]
        )
        mock_dlq.delete_messages.assert_called_once_with(
            Entries=[
                {'Id': queue_message.message_id, 'ReceiptHandle': queue_message.receipt_handle}
                for queue_message in messages
            ]
        )

    def test_partial_failure_requeue_dead_letter(self, sqs_consumer):
        num_messages = 1
        visibility_timeout = 4
        queue_name = "HEDWIG-DEV-RTEP"

        messages = [mock.MagicMock() for _ in range(num_messages)]
        sqs_consumer.pull_messages = mock.MagicMock(side_effect=iter([messages, None]))
        dlq_name = f'{queue_name}-DLQ'

        mock_queue, mock_dlq = mock.MagicMock(), mock.MagicMock()
        mock_queue.attributes = {'RedrivePolicy': json.dumps({'deadLetterTargetArn': dlq_name})}
        mock_queue.send_messages.return_value = {'Successful': ['success_id'], 'Failed': ["fail_id"]}
        sqs_consumer._get_queue_by_name = mock.MagicMock(side_effect=iter([mock_queue, mock_dlq]))

        with pytest.raises(PartialFailure):
            sqs_consumer.requeue_dead_letter(num_messages=num_messages, visibility_timeout=visibility_timeout)

    def test_fetch_and_process_messages_success(
        self, sqs_consumer, message, prepost_process_hooks, use_transport_message_attrs
    ):
        shutdown_event = threading.Event()
        num_messages = 3
        visibility_timeout = 4
        queue = mock.MagicMock()
        sqs_consumer.sqs_resource.get_queue_by_name = mock.MagicMock(return_value=queue)

        receipt = "receipt"
        sent_time = datetime.now(timezone.utc)
        first_receive_time = datetime.now(timezone.utc)
        receive_count = 1

        queue_message = mock.MagicMock()
        queue_message.receipt_handle = receipt
        payload, message_attributes = message.serialize()
        if isinstance(payload, bytes):
            queue_message.body = base64.encodebytes(payload).decode()
            message_attributes['hedwig_encoding'] = 'base64'
        else:
            queue_message.body = payload
        queue_message.message_attributes = {
            k: {'DataType': 'String', 'StringValue': v} for k, v in message_attributes.items()
        }
        queue_message.attributes = {
            'ApproximateReceiveCount': receive_count,
            'SentTimestamp': int(sent_time.timestamp() * 1000),
            'ApproximateFirstReceiveTimestamp': int(first_receive_time.timestamp() * 1000),
        }

        mock_return_once(queue.receive_messages, [queue_message], [], shutdown_event)
        message_mock = mock.MagicMock()
        sqs_consumer._build_message = mock.MagicMock(return_value=message_mock)
        sqs_consumer.process_message = mock.MagicMock(wraps=sqs_consumer.process_message)
        sqs_consumer.message_handler = mock.MagicMock(wraps=sqs_consumer.message_handler)

        sqs_consumer.fetch_and_process_messages(num_messages, visibility_timeout, shutdown_event)

        sqs_consumer.sqs_resource.get_queue_by_name.assert_called_with(QueueName=sqs_consumer.queue_name)
        queue.receive_messages.assert_called_with(
            MaxNumberOfMessages=num_messages,
            MessageAttributeNames=['All'],
            AttributeNames=['All'],
            VisibilityTimeout=visibility_timeout,
            WaitTimeSeconds=sqs_consumer.WAIT_TIME_SECONDS,
        )
        sqs_consumer.process_message.assert_called_once_with(queue_message)
        sqs_consumer.message_handler.assert_called_once_with(
            payload,
            message_attributes,
            AWSMetadata(
                receipt,
                # truncates to millisecond precision
                first_receive_time.replace(microsecond=(first_receive_time.microsecond // 1000) * 1000),
                sent_time.replace(microsecond=(sent_time.microsecond // 1000) * 1000),
                receive_count,
            ),
        )
        message_mock.exec_callback.assert_called_once_with()
        queue_message.delete.assert_called_once_with()
        pre_process_hook.assert_called_once_with(sqs_queue_message=queue_message)
        post_process_hook.assert_called_once_with(sqs_queue_message=queue_message)


class TestSNSConsumer:
    @mock.patch('hedwig.backends.aws.AWSSNSConsumerBackend.process_message')
    def test_process_messages(self, mock_process_message, sns_consumer):
        records = {"attributes": {}}, {"attributes": {}}
        event = {'Records': records}

        sns_consumer.process_messages(event)

        mock_process_message.assert_has_calls([mock.call(r) for r in records])

    def test_success_process_message(self, sns_consumer, prepost_process_hooks, use_transport_message_attrs):
        # copy from https://docs.aws.amazon.com/lambda/latest/dg/eventsources.html#eventsources-sns
        mock_record = {
            "EventVersion": "1.0",
            "EventSubscriptionArn": "arn",
            "EventSource": "aws:sns",
            "Sns": {
                "SignatureVersion": "1",
                "Timestamp": "1970-01-01T00:00:00.000Z",
                "Signature": "EXAMPLE",
                "SigningCertUrl": "EXAMPLE",
                "MessageId": "95df01b4-ee98-5cb9-9903-4c221d41eb5e",
                "Message": "Hello from SNS!",
                "MessageAttributes": {
                    "request_id": {"Type": "String", "Value": str(uuid.uuid4())},
                    "TestBinary": {"Type": "Binary", "Value": "TestBinary"},
                },
                "Type": "Notification",
                "UnsubscribeUrl": "EXAMPLE",
                "TopicArn": "arn",
                "Subject": "TestInvoke",
            },
        }
        message_mock = mock.MagicMock()
        sns_consumer._build_message = mock.MagicMock(return_value=message_mock)

        sns_consumer.process_message(mock_record)

        sns_consumer._build_message.assert_called_once_with(
            mock_record['Sns']['Message'],
            {k: o['Value'] for k, o in mock_record['Sns']['MessageAttributes'].items()},
            None,
        )
        pre_process_hook.assert_called_once_with(sns_record=mock_record)
        post_process_hook.assert_called_once_with(sns_record=mock_record)
        message_mock.exec_callback.assert_called_once_with()

    def test_success_process_message_base64(self, sns_consumer, prepost_process_hooks, use_transport_message_attrs):
        # copy from https://docs.aws.amazon.com/lambda/latest/dg/eventsources.html#eventsources-sns
        mock_record = {
            "EventVersion": "1.0",
            "EventSubscriptionArn": "arn",
            "EventSource": "aws:sns",
            "Sns": {
                "SignatureVersion": "1",
                "Timestamp": "1970-01-01T00:00:00.000Z",
                "Signature": "EXAMPLE",
                "SigningCertUrl": "EXAMPLE",
                "MessageId": "95df01b4-ee98-5cb9-9903-4c221d41eb5e",
                "Message": "OTVkZjAxYjQtZWU5OC01Y2I5LTk5MDMtNGMyMjFkNDFlYjVl",
                "MessageAttributes": {
                    "request_id": {"Type": "String", "Value": str(uuid.uuid4())},
                    "TestBinary": {"Type": "Binary", "Value": "TestBinary"},
                    "hedwig_encoding": {"Type": "String", "Value": "base64"},
                },
                "Type": "Notification",
                "UnsubscribeUrl": "EXAMPLE",
                "TopicArn": "arn",
                "Subject": "TestInvoke",
            },
        }
        message_mock = mock.MagicMock()
        sns_consumer._build_message = mock.MagicMock(return_value=message_mock)

        sns_consumer.process_message(mock_record)

        sns_consumer._build_message.assert_called_once_with(
            base64.decodebytes(mock_record['Sns']['Message'].encode()).decode(),
            {k: o['Value'] for k, o in mock_record['Sns']['MessageAttributes'].items()},
            None,
        )
        pre_process_hook.assert_called_once_with(sns_record=mock_record)
        post_process_hook.assert_called_once_with(sns_record=mock_record)
        message_mock.exec_callback.assert_called_once_with()
