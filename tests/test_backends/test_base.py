import copy
import json
import math
from decimal import Decimal
from unittest import mock

import pytest

from hedwig.backends import base
from hedwig.backends.base import HedwigBaseBackend, HedwigConsumerBaseBackend, HedwigPublisherBaseBackend
from hedwig.backends.utils import get_consumer_backend, get_publisher_backend
from hedwig.models import Message, ValidationError
from hedwig.exceptions import LoggingException, RetryException, IgnoreException
from tests.utils import mock_return_once


class MockBackend(HedwigConsumerBaseBackend, HedwigPublisherBaseBackend):
    pass


class TestBackends:
    def test_success_get_consumer_backend(self, settings):
        settings.HEDWIG_CONSUMER_BACKEND = "tests.test_backends.test_base.MockBackend"

        consumer_backend = get_consumer_backend()

        assert isinstance(consumer_backend, MockBackend)

    def test_success_get_publisher_backend(self, settings):
        settings.HEDWIG_PUBLISHER_BACKEND = "tests.test_backends.test_base.MockBackend"

        publisher_backend = get_publisher_backend()

        assert isinstance(publisher_backend, MockBackend)

    @pytest.mark.parametrize("get_backend_fn", [get_publisher_backend, get_consumer_backend])
    def test_failure(self, get_backend_fn, settings):
        settings.HEDWIG_PUBLISHER_BACKEND = settings.HEDWIG_CONSUMER_BACKEND = "hedwig.backends.invalid"

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
    def test_success(self, consumer_backend, timed_shutdown_event):
        num_messages = 3
        visibility_timeout = 4

        consumer_backend.pull_messages = mock.MagicMock()
        consumer_backend.pull_messages.return_value = [mock.MagicMock(), mock.MagicMock()]
        consumer_backend.process_message = mock.MagicMock()
        consumer_backend.ack_message = mock.MagicMock()

        consumer_backend.fetch_and_process_messages(num_messages, visibility_timeout, timed_shutdown_event)

        consumer_backend.pull_messages.assert_called_with(
            num_messages=num_messages, visibility_timeout=visibility_timeout, shutdown_event=timed_shutdown_event
        )
        consumer_backend.process_message.assert_has_calls(
            [mock.call(x) for x in consumer_backend.pull_messages.return_value]
        )
        consumer_backend.ack_message.assert_has_calls(
            [mock.call(x) for x in consumer_backend.pull_messages.return_value]
        )

    def test_preserves_messages(self, consumer_backend, timed_shutdown_event):
        consumer_backend.pull_messages = mock.MagicMock()
        consumer_backend.pull_messages.return_value = [mock.MagicMock()]
        consumer_backend.process_message = mock.MagicMock()
        consumer_backend.process_message.side_effect = Exception

        consumer_backend.fetch_and_process_messages(shutdown_event=timed_shutdown_event)

        consumer_backend.pull_messages.return_value[0].delete.assert_not_called()

    def test_ignore_delete_error(self, consumer_backend, timed_shutdown_event):
        queue_message = mock.MagicMock()
        consumer_backend.pull_messages = mock.MagicMock()
        mock_return_once(consumer_backend.pull_messages, [queue_message], [])
        consumer_backend.process_message = mock.MagicMock()
        consumer_backend.ack_message = mock.MagicMock(side_effect=Exception)

        with mock.patch.object(base.logger, 'exception') as logging_mock:
            consumer_backend.fetch_and_process_messages(shutdown_event=timed_shutdown_event)

            logging_mock.assert_called_once()

        consumer_backend.ack_message.assert_called_once_with(queue_message)

    def test_pre_process_hook(self, consumer_backend, settings, timed_shutdown_event):
        pre_process_hook.reset_mock()
        settings.HEDWIG_PRE_PROCESS_HOOK = 'tests.test_backends.test_base.pre_process_hook'
        consumer_backend.pull_messages = mock.MagicMock(return_value=[mock.MagicMock(), mock.MagicMock()])

        consumer_backend.fetch_and_process_messages(shutdown_event=timed_shutdown_event)

        pre_process_hook.assert_has_calls(
            [
                mock.call(**consumer_backend.pre_process_hook_kwargs(x))
                for x in consumer_backend.pull_messages.return_value
            ]
        )

    def test_post_process_hook(self, consumer_backend, settings, timed_shutdown_event):
        post_process_hook.reset_mock()
        settings.HEDWIG_POST_PROCESS_HOOK = 'tests.test_backends.test_base.post_process_hook'
        consumer_backend.process_message = mock.MagicMock()
        consumer_backend.pull_messages = mock.MagicMock(return_value=[mock.MagicMock(), mock.MagicMock()])

        consumer_backend.fetch_and_process_messages(shutdown_event=timed_shutdown_event)

        post_process_hook.assert_has_calls(
            [
                mock.call(**consumer_backend.post_process_hook_kwargs(x))
                for x in consumer_backend.pull_messages.return_value
            ]
        )

    def test_post_process_hook_exception_raised(self, consumer_backend, settings, timed_shutdown_event):
        settings.HEDWIG_POST_PROCESS_HOOK = 'tests.test_backends.test_base.post_process_hook'
        consumer_backend.process_message = mock.MagicMock()
        mock_message = mock.MagicMock()
        consumer_backend.pull_messages = mock.MagicMock()
        mock_return_once(consumer_backend.pull_messages, [mock_message], [])
        post_process_hook.reset_mock()
        post_process_hook.side_effect = RuntimeError('fail')

        consumer_backend.fetch_and_process_messages(shutdown_event=timed_shutdown_event)

        post_process_hook.assert_called_once_with(**consumer_backend.pre_process_hook_kwargs(mock_message))
        mock_message.delete.assert_not_called()


@pytest.mark.parametrize('value', [1469056316326, 1469056316326.123])
def test__convert_to_json_decimal(value, message_data):
    backend = HedwigBaseBackend()
    message_data['data']['decimal'] = Decimal(value)
    message = Message(message_data)
    assert json.loads(backend.message_payload(message.as_dict()))['data']['decimal'] == float(message.data['decimal'])


@pytest.mark.parametrize('value', [math.nan, math.inf, -math.inf])
def test__convert_to_json_disallow_nan(value, message_data):
    backend = HedwigBaseBackend()
    message_data['data']['nan'] = value
    message = Message(message_data)
    with pytest.raises(ValueError):
        backend.message_payload(message.as_dict())


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
