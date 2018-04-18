import json
from unittest import mock
import uuid

import pytest

from hedwig import consumer
from hedwig.consumer import (
    get_queue, _load_and_validate_message, get_default_queue_name, message_handler, listen_for_messages,
    message_handler_lambda, process_messages_for_lambda_consumer, message_handler_sqs, get_queue_messages,
    WAIT_TIME_SECONDS, fetch_and_process_messages
)
from hedwig.conf import settings
from hedwig.exceptions import RetryException, ValidationError


@mock.patch('hedwig.consumer._get_sqs_resource', autospec=True)
def test_get_queue(mock_get_sqs_resource):
    queue_name = 'foo'
    assert mock_get_sqs_resource.return_value.get_queue_by_name.return_value == get_queue(queue_name)
    mock_get_sqs_resource.assert_called_once_with()
    mock_get_sqs_resource.return_value.get_queue_by_name.assert_called_once_with(QueueName=queue_name)


@mock.patch('hedwig.consumer.Message', autospec=True)
def test__load_and_validate_message(mock_message, message_data):
    _load_and_validate_message(message_data)
    mock_message.assert_called_once_with(message_data)
    mock_message.return_value.validate.assert_called_once_with()


@mock.patch('hedwig.consumer.Message.exec_callback', autospec=True)
@mock.patch('hedwig.consumer._load_and_validate_message', autospec=True)
class TestMessageHandler:
    def test_success(self, mock_load_and_validate_message, mock_call_task, message_data, message):
        mock_load_and_validate_message.return_value = message
        receipt = str(uuid.uuid4())
        message_handler(json.dumps(message_data), receipt)
        mock_load_and_validate_message.assert_called_once_with(message_data)
        mock_call_task.assert_called_once_with(message)

    def test_fails_on_invalid_json(self, *mocks):
        with pytest.raises(ValueError):
            message_handler("bad json", None)

    def test_fails_on_validation_error(self, mock_load_and_validate_message, mock_call_task, message_data):
        error_message = 'Invalid message body'
        mock_load_and_validate_message.side_effect = ValidationError(error_message)
        with pytest.raises(ValidationError):
            message_handler(json.dumps(message_data), None)
        mock_call_task.assert_not_called()

    def test_fails_on_task_failure(self, mock_load_and_validate_message, mock_call_task, message_data, message):
        mock_load_and_validate_message.return_value = message
        mock_call_task.side_effect = Exception
        with pytest.raises(mock_call_task.side_effect):
            message_handler(json.dumps(message_data), None)

    def test_post_deserialize_hook(
            self, mock_load_and_validate_message, mock_call_task, message_data, message, settings):
        settings.HEDWIG_POST_DESERIALIZE_HOOK = 'tests.test_consumer.post_deserialize_hook'

        mock_load_and_validate_message.return_value = message
        receipt = str(uuid.uuid4())
        message_handler(json.dumps(message_data), receipt)
        mock_load_and_validate_message.assert_called_once_with(message_data)
        mock_call_task.assert_called_once_with(message)

        post_deserialize_hook.assert_called_once_with(message_data=message_data)


@mock.patch('hedwig.consumer.message_handler', autospec=True)
def test_message_handler_sqs(mock_message_handler):
    queue_message = mock.MagicMock()
    message_handler_sqs(queue_message)

    mock_message_handler.assert_called_once_with(queue_message.body, queue_message.receipt_handle)


@mock.patch('hedwig.consumer.message_handler', autospec=True)
def test_message_handler_lambda(mock_message_handler):
    lambda_event = mock.MagicMock()
    message_handler_lambda(lambda_event)

    mock_message_handler.assert_called_once_with(lambda_event['Sns']['Message'], None)


def test_get_queue_messages():
    queue = mock.MagicMock()
    num_messages = 2
    visibility_timeout = 100

    messages = get_queue_messages(queue, num_messages, visibility_timeout=visibility_timeout)

    queue.receive_messages.assert_called_once_with(
        MaxNumberOfMessages=num_messages,
        WaitTimeSeconds=WAIT_TIME_SECONDS,
        MessageAttributeNames=['All'],
        VisibilityTimeout=visibility_timeout,
    )
    assert messages == queue.receive_messages.return_value


def test_get_default_queue_name():
    assert get_default_queue_name() == f'HEDWIG-{settings.HEDWIG_QUEUE.upper()}'


pre_process_hook = mock.MagicMock()
post_deserialize_hook = mock.MagicMock()


@mock.patch('hedwig.consumer.get_queue_messages', autospec=True)
@mock.patch('hedwig.consumer.message_handler_sqs', autospec=True)
class TestFetchAndProcessMessages:
    def test_success(self, mock_message_handler, mock_get_messages):
        queue_name = 'my-queue'
        queue = mock.MagicMock()
        num_messages = 3
        visibility_timeout = 4

        mock_get_messages.return_value = [mock.MagicMock(), mock.MagicMock()]

        fetch_and_process_messages(queue_name, queue, num_messages, visibility_timeout)

        mock_get_messages.assert_called_once_with(queue, num_messages, visibility_timeout=visibility_timeout)
        mock_message_handler.assert_has_calls([mock.call(x) for x in mock_get_messages.return_value])
        for message in mock_get_messages.return_value:
            message.delete.assert_called_once_with()

    def test_logs_exceptions_and_preserves_messages(self, mock_message_handler, mock_get_messages):
        queue_name = 'my-queue'
        queue = mock.MagicMock()

        mock_get_messages.return_value = [mock.MagicMock()]
        mock_message_handler.side_effect = Exception

        with mock.patch.object(consumer.logger, 'exception') as logging_mock:
            fetch_and_process_messages(queue_name, queue)

            logging_mock.assert_called_once()

        mock_get_messages.return_value[0].delete.assert_not_called()

    def test_special_handling_retry_error(self, mock_message_handler, mock_get_messages):
        queue_name = 'my-queue'
        queue = mock.MagicMock()

        mock_get_messages.return_value = [mock.MagicMock()]
        mock_message_handler.side_effect = RetryException

        with mock.patch.object(consumer.logger, 'info') as logging_mock:
            fetch_and_process_messages(queue_name, queue)

            logging_mock.assert_called_once()

        mock_get_messages.return_value[0].delete.assert_not_called()

    def test_ignore_delete_error(self, mock_message_handler, mock_get_messages):
        queue_name = 'my-queue'
        queue = mock.MagicMock()

        mock_get_messages.return_value = [mock.MagicMock()]
        mock_get_messages.return_value[0].delete.side_effect = Exception

        with mock.patch.object(consumer.logger, 'exception') as logging_mock:
            fetch_and_process_messages(queue_name, queue)

            logging_mock.assert_called_once()

        mock_get_messages.return_value[0].delete.assert_called_once_with()

    def test_pre_process_hook(self, mock_message_handler, mock_get_messages, settings):
        queue_name = 'my-queue'
        queue = mock.MagicMock()
        settings.HEDWIG_PRE_PROCESS_HOOK = 'tests.test_consumer.pre_process_hook'

        mock_get_messages.return_value = [mock.MagicMock(), mock.MagicMock()]

        fetch_and_process_messages(queue_name, queue)

        pre_process_hook.assert_has_calls([
            mock.call(sqs_queue_message=x)
            for x in mock_get_messages.return_value
        ])


@mock.patch('hedwig.consumer.message_handler_lambda', autospec=True)
class TestProcessMessagesForLambdaConsumer:
    def assert_extra_logged(self, logging_mock, expected):
        actual = logging_mock.call_args[1]['extra']
        assert actual == expected

    def test_success(self, mock_message_handler):
        # copy from https://docs.aws.amazon.com/lambda/latest/dg/eventsources.html#eventsources-sns
        mock_record1 = {
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
                    "request_id": {
                        "Type": "String",
                        "Value": str(uuid.uuid4())
                    },
                    "TestBinary": {
                        "Type": "Binary",
                        "Value": "TestBinary"
                    }
                },
                "Type": "Notification",
                "UnsubscribeUrl": "EXAMPLE",
                "TopicArn": "arn",
                "Subject": "TestInvoke"
            }
        }
        mock_record2 = {
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
                    "request_id": {
                        "Type": "String",
                        "Value": str(uuid.uuid4())
                    },
                    "TestBinary": {
                        "Type": "Binary",
                        "Value": "TestBinary"
                    }
                },
                "Type": "Notification",
                "UnsubscribeUrl": "EXAMPLE",
                "TopicArn": "arn",
                "Subject": "TestInvoke"
            }
        }
        event = {
            "Records": [
                mock_record1,
                mock_record2
            ]
        }
        process_messages_for_lambda_consumer(event)
        mock_message_handler.assert_has_calls([
            mock.call(mock_record1),
            mock.call(mock_record2),
        ])

    def test_logs_and_preserves_message(self, mock_handler):
        event = {'Records': [mock.MagicMock()]}
        mock_handler.side_effect = RuntimeError
        with mock.patch.object(consumer.logger, 'exception') as logging_mock:
            with pytest.raises(RuntimeError):
                process_messages_for_lambda_consumer(event)
            self.assert_extra_logged(logging_mock, None)


@mock.patch('hedwig.consumer.get_queue', autospec=True)
@mock.patch('hedwig.consumer.fetch_and_process_messages', autospec=True)
class TestListenForMessages:
    def test_listen_for_messages(self, mock_fetch_and_process, mock_get_queue):
        num_messages = 3
        visibility_timeout_s = 4
        loop_count = 1

        listen_for_messages(num_messages, visibility_timeout_s, loop_count)

        queue_name = get_default_queue_name()
        mock_get_queue.assert_called_once_with(queue_name)
        mock_fetch_and_process.assert_called_once_with(
            queue_name, mock_get_queue.return_value, num_messages=num_messages,
            visibility_timeout=visibility_timeout_s,
        )
