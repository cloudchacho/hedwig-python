from distutils.version import StrictVersion
import random
from unittest import mock

import pytest

from hedwig.exceptions import ValidationError, CallbackNotFound
from hedwig.models import Message

from tests.models import MessageType


class TestMessageMethods:
    publisher = 'myapi'

    def test_new(self, message_data):
        message = Message.new(
            MessageType.trip_created,
            StrictVersion('1.0'),
            message_data['data'],
            message_data['id'],
            message_data['metadata']['headers'],
        )

        assert message.id == message_data['id']
        assert message.version == StrictVersion('1.0')
        assert message.headers == message_data['metadata']['headers']
        assert message.type == 'trip_created'
        assert message.data == message_data['data']

    @mock.patch('hedwig.callback.Callback.find_by_message', side_effect=CallbackNotFound)
    def test_validate_missing_task(self, _, message):
        with pytest.raises(ValidationError):
            _ = message.callback

    @mock.patch('tests.handlers._trip_created_handler', autospec=True)
    def test_exec_callback(self, mock_trip_created_handler, message):
        message.exec_callback()
        mock_trip_created_handler.assert_called_once_with(message)

    @mock.patch('hedwig.models.get_consumer_backend')
    def test_extend_visibility_timeout(self, mock_get_consumer_backend, message):
        visibility_timeout_s = random.randint(0, 1000)

        message.extend_visibility_timeout(visibility_timeout_s)

        mock_get_consumer_backend.assert_called_once_with()

        mock_get_consumer_backend.return_value.extend_visibility_timeout.assert_called_once_with(
            visibility_timeout_s, message.provider_metadata
        )

    def test_getter_timestamp(self, message):
        assert message.timestamp == message.metadata.timestamp

    def test_getter_publisher(self, message):
        assert message.publisher == message.metadata.publisher
