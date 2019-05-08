import copy
import json
from decimal import Decimal
from unittest import mock

import pytest

from hedwig.backends.base import HedwigBaseBackend
from hedwig.models import Message, ValidationError
from hedwig.exceptions import LoggingException, RetryException, IgnoreException
from hedwig.backends import base
from hedwig.backends.aws import AWSSQSConsumerBackend, AWSSNSPublisherBackend
from hedwig.backends.utils import get_consumer_backend, get_publisher_backend


class TestBackends:
    def test_success_get_consumer_backend(self, mock_boto3, settings):
        settings.HEDWIG_CONSUMER_BACKEND = "hedwig.backends.aws.AWSSQSConsumerBackend"

        consumer_backend = get_consumer_backend()

        assert isinstance(consumer_backend, AWSSQSConsumerBackend)

    def test_success_get_publisher_backend(self, mock_boto3, settings):
        settings.HEDWIG_PUBLISHER_BACKEND = "hedwig.backends.aws.AWSSNSPublisherBackend"

        consumer_backend = get_publisher_backend()

        assert isinstance(consumer_backend, AWSSNSPublisherBackend)

    @pytest.mark.parametrize("get_backend_fn", [get_publisher_backend, get_consumer_backend])
    def test_failure(self, get_backend_fn, mock_boto3, settings):
        settings.HEDWIG_PUBLISHER_BACKEND = settings.HEDWIG_CONSUMER_BACKEND = "hedwig.backends.aws.Invalid"

        with pytest.raises(ImportError):
            get_backend_fn()


@mock.patch('hedwig.backends.base.Message.exec_callback', autospec=True)
class TestMessageHandler:
    def test_success(self, mock_exec_callback, message_data, message, consumer_backend):
        provider_metadata = mock.Mock()
        consumer_backend.message_handler(json.dumps(message_data), provider_metadata)
        mock_exec_callback.assert_called_once_with(message)

    def test_fails_on_invalid_json(self, mock_exec_callback, consumer_backend):
        with pytest.raises(ValueError):
            consumer_backend.message_handler("bad json", None)

    @mock.patch('hedwig.backends.base.Message.validate', autospec=True)
    def test_fails_on_validation_error(self, mock_validate, mock_exec_callback, message_data, consumer_backend):
        error_message = 'Invalid message body'
        mock_validate.side_effect = ValidationError(error_message)
        with pytest.raises(ValidationError):
            consumer_backend.message_handler(json.dumps(message_data), None)
        mock_exec_callback.assert_not_called()

    def test_fails_on_task_failure(self, mock_exec_callback, message_data, message, consumer_backend):
        mock_exec_callback.side_effect = Exception
        with pytest.raises(mock_exec_callback.side_effect):
            consumer_backend.message_handler(json.dumps(message_data), None)

    def test_special_handling_logging_error(self, mock_exec_callback, message_data, message, consumer_backend):
        mock_exec_callback.side_effect = LoggingException('foo', extra={'mickey': 'mouse'})
        with pytest.raises(LoggingException), mock.patch.object(base.logger, 'exception') as logging_mock:
            consumer_backend.message_handler(json.dumps(message_data), None)

            logging_mock.assert_called_once_with('foo', extra={'mickey': 'mouse'})

    def test_special_handling_retry_error(self, mock_exec_callback, message_data, message, consumer_backend):
        mock_exec_callback.side_effect = RetryException
        with pytest.raises(mock_exec_callback.side_effect), mock.patch.object(base.logger, 'info') as logging_mock:
            consumer_backend.message_handler(json.dumps(message_data), None)

            logging_mock.assert_called_once()

    def test_special_handling_ignore_exception(self, mock_exec_callback, message_data, message, consumer_backend):
        mock_exec_callback.side_effect = IgnoreException
        # no exception raised
        with mock.patch.object(base.logger, 'info') as logging_mock:
            consumer_backend.message_handler(json.dumps(message_data), None)

            logging_mock.assert_called_once()


pre_process_hook = mock.MagicMock()
post_process_hook = mock.MagicMock()


class TestFetchAndProcessMessages:
    def test_success(self, consumer_backend):
        num_messages = 3
        visibility_timeout = 4

        consumer_backend.pull_messages = mock.MagicMock()
        consumer_backend.pull_messages.return_value = [mock.MagicMock(), mock.MagicMock()]
        consumer_backend.process_message = mock.MagicMock()
        consumer_backend.delete_message = mock.MagicMock()

        consumer_backend.fetch_and_process_messages(num_messages, visibility_timeout)

        consumer_backend.pull_messages.assert_called_once_with(num_messages, visibility_timeout)
        consumer_backend.process_message.assert_has_calls(
            [mock.call(x) for x in consumer_backend.pull_messages.return_value]
        )
        consumer_backend.delete_message.assert_has_calls(
            [mock.call(x) for x in consumer_backend.pull_messages.return_value]
        )

    def test_preserves_messages(self, consumer_backend):
        consumer_backend.pull_messages = mock.MagicMock()
        consumer_backend.pull_messages.return_value = [mock.MagicMock()]
        consumer_backend.process_message = mock.MagicMock()
        consumer_backend.process_message.side_effect = Exception

        consumer_backend.fetch_and_process_messages()

        consumer_backend.pull_messages.return_value[0].delete.assert_not_called()

    def test_ignore_delete_error(self, consumer_backend):
        queue_message = mock.MagicMock()
        consumer_backend.pull_messages = mock.MagicMock(return_value=[queue_message])
        consumer_backend.process_message = mock.MagicMock()
        consumer_backend.delete_message = mock.MagicMock(side_effect=Exception)

        with mock.patch.object(base.logger, 'exception') as logging_mock:
            consumer_backend.fetch_and_process_messages()

            logging_mock.assert_called_once()

        consumer_backend.delete_message.assert_called_once_with(consumer_backend.pull_messages.return_value[0])

    def test_pre_process_hook(self, consumer_backend, settings):
        pre_process_hook.reset_mock()
        settings.HEDWIG_PRE_PROCESS_HOOK = 'tests.test_backends.test_base.pre_process_hook'
        consumer_backend.pull_messages = mock.MagicMock(return_value=[mock.MagicMock(), mock.MagicMock()])

        consumer_backend.fetch_and_process_messages()

        pre_process_hook.assert_has_calls(
            [
                mock.call(**consumer_backend.pre_process_hook_kwargs(x))
                for x in consumer_backend.pull_messages.return_value
            ]
        )

    def test_post_process_hook(self, consumer_backend, settings):
        post_process_hook.reset_mock()
        settings.HEDWIG_POST_PROCESS_HOOK = 'tests.test_backends.test_base.post_process_hook'
        consumer_backend.process_message = mock.MagicMock()
        consumer_backend.pull_messages = mock.MagicMock(return_value=[mock.MagicMock(), mock.MagicMock()])

        consumer_backend.fetch_and_process_messages()

        post_process_hook.assert_has_calls(
            [
                mock.call(**consumer_backend.post_process_hook_kwargs(x))
                for x in consumer_backend.pull_messages.return_value
            ]
        )

    def test_post_process_hook_exception_raised(self, consumer_backend, settings):
        settings.HEDWIG_POST_PROCESS_HOOK = 'tests.test_backends.test_base.post_process_hook'
        consumer_backend.process_message = mock.MagicMock()
        mock_message = mock.MagicMock()
        consumer_backend.pull_messages = mock.MagicMock(return_value=[mock_message])
        post_process_hook.reset_mock()
        post_process_hook.side_effect = RuntimeError('fail')

        consumer_backend.fetch_and_process_messages()

        post_process_hook.assert_called_once_with(**consumer_backend.pre_process_hook_kwargs(mock_message))
        mock_message.delete.assert_not_called()


@pytest.mark.parametrize('value', [1469056316326, 1469056316326.123])
def test__convert_to_json_decimal(value, message_data):
    backend = HedwigBaseBackend()
    message_data['data']['decimal'] = Decimal(value)
    message = Message(message_data)
    assert json.loads(backend.message_payload(message.as_dict()))['data']['decimal'] == float(message.data['decimal'])


def test__convert_to_json_non_serializable(message_data):
    backend = HedwigBaseBackend()
    message_data['data']['decimal'] = object()
    message = Message(message_data)
    with pytest.raises(TypeError):
        backend.message_payload(message.as_dict())


default_headers_hook = mock.MagicMock()


def pre_serialize_hook(message_data):
    # clear headers to make sure we are not able to destroy message attributes
    message_data['metadata']['headers'].clear()


class TestPublisher:
    def test_publish(self, message, mock_publisher_backend):
        message.validate()

        mock_publisher_backend.publish(message)

        payload = message.as_dict()
        payload['metadata']['headers'] = message.headers
        payload = json.dumps(payload)

        mock_publisher_backend._publish.assert_called_once_with(message, payload, message.headers)

    def test_default_headers_hook(self, message, mock_publisher_backend, settings):
        settings.HEDWIG_DEFAULT_HEADERS = 'tests.test_backends.test_base.default_headers_hook'
        default_headers_hook.return_value = {'mickey': 'mouse'}

        message.validate()

        mock_publisher_backend.publish(message)

        default_headers_hook.assert_called_once_with(message=message)

        payload = message.as_dict()
        headers = payload['metadata']['headers'] = {**message.headers, **default_headers_hook.return_value}

        mock_publisher_backend._publish.assert_called_once_with(message, mock.ANY, headers)
        assert json.loads(mock_publisher_backend._publish.call_args[0][1]) == payload

    def test_pre_serialize_hook(self, message, mock_publisher_backend, settings):
        settings.HEDWIG_PRE_SERIALIZE_HOOK = 'tests.test_backends.test_base.pre_serialize_hook'

        message.validate()

        headers = copy.copy(message.headers)

        mock_publisher_backend.publish(message)

        payload = message.as_dict()
        payload['metadata']['headers'].clear()
        payload = json.dumps(payload)

        mock_publisher_backend._publish.assert_called_once_with(message, payload, headers)
