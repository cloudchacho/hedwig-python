from distutils.version import StrictVersion
import random
import time
from unittest import mock
import uuid

import pytest

from hedwig.conf import settings
from hedwig import ValidationError, CallbackNotFound, MessageType
from hedwig.models import Message, Metadata
from hedwig.testing.factories import MetadataFactory


class TestMetadata:
    def test_new(self):
        data = MetadataFactory()
        metadata = Metadata(data)
        assert metadata.timestamp == data['timestamp']
        assert metadata.headers == data['headers']
        assert metadata.publisher == data['publisher']
        assert metadata.receipt is None


class TestMessageMethods:
    publisher = 'myapi'

    @mock.patch('hedwig.models.time.time', autospec=True)
    def test_create_metadata(self, mock_time):
        mock_time.return_value = time.time()
        headers = {
            'foo': 'bar',
        }

        assert Message._create_metadata(headers) == {
            'timestamp': int(mock_time.return_value * 1000),
            'publisher': settings.HEDWIG_PUBLISHER,
            'headers': headers,
        }

    def test_constructor(self):
        message_data = {
            "id": str(uuid.uuid4()),
            "metadata": {
                "timestamp": 1460868253255,
                "publisher": "myapp",
                "headers": {
                    "request_id": str(uuid.uuid4()),
                },
            },
            "format_version": "1.0",
            "schema": "https://hedwig.automatic.com/schema#/schemas/trip.created/1.0",
            "data": {
                "from": "example@email.com",
                "subject": "Hello!"
            }
        }

        message = Message(message_data)
        assert message.id == message_data['id']
        assert message.metadata == Metadata(message_data['metadata'])
        assert message.headers == message_data['metadata']['headers']
        assert message.schema == 'https://hedwig.automatic.com/schema#/schemas/trip.created/1.0'
        assert message.data == message_data['data']

    def test_new(self, message_data):
        message = Message.new(
            MessageType.trip_created, StrictVersion('1.0'), message_data['data'], message_data['id'],
            message_data['metadata']['headers'],
        )

        assert message.id == message_data['id']
        assert message.format_version == Message.FORMAT_CURRENT_VERSION
        assert message.headers == message_data['metadata']['headers']
        assert message.schema == 'https://hedwig.automatic.com/schema#/schemas/trip_created/1.0'
        assert message.data == message_data['data']

    def test_as_dict(self, message):
        assert message.as_dict() == {
            'format_version': str(message.format_version),
            'id': message.id,
            'metadata': message.metadata.as_dict(),
            'schema': message.schema,
            'data': message.data,
        }

    def test_validate_callback(self, message):
        message.validate()
        message.validate_callback()
        assert message.callback is not None

    @pytest.mark.parametrize('missing_data', ['id', 'metadata', 'format_version', 'schema', 'data'])
    def test_validate_missing_data(self, missing_data, message_data):
        message_data[missing_data] = None

        with pytest.raises(ValidationError):
            Message(message_data)

    def test_validate_invalid_version(self, message_data):
        message_data['format_version'] = '3.0'

        with pytest.raises(ValidationError):
            Message(message_data)

    @mock.patch('hedwig.callback.Callback.find_by_message', side_effect=CallbackNotFound)
    def test_validate_missing_task(self, _, message):
        message.validate()
        with pytest.raises(ValidationError):
            message.validate_callback()

    @mock.patch('tests.handlers._trip_created_handler', autospec=True)
    def test_exec_callback(self, mock_trip_created_handler, message):
        message.validate()
        message.validate_callback()
        message.metadata.receipt = str(uuid.uuid4())
        message.exec_callback()
        mock_trip_created_handler.assert_called_once_with(message)

    @mock.patch('hedwig.models._get_sqs_client')
    @mock.patch('hedwig.consumer.get_default_queue_name')
    def test_extend_visibility_timeout(self, mock_get_queue_name, mock_get_sqs_client, message):
        visibility_timeout_s = random.randint(0, 1000)

        message.extend_visibility_timeout(visibility_timeout_s)

        mock_get_queue_name.assert_called_once_with()
        mock_get_sqs_client.assert_called_once_with()
        mock_get_sqs_client.return_value.get_queue_url.assert_called_once_with(
            QueueName=mock_get_queue_name.return_value
        )
        mock_get_sqs_client.return_value.change_message_visibility.assert_called_once_with(
            QueueUrl=mock_get_sqs_client.return_value.get_queue_url.return_value['QueueUrl'],
            ReceiptHandle=message.receipt,
            VisibilityTimeout=visibility_timeout_s,
        )
