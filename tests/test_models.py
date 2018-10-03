from distutils.version import StrictVersion
import random
import time
from unittest import mock
import uuid

import pytest

from hedwig.conf import settings
from hedwig.exceptions import ValidationError, CallbackNotFound
from hedwig.models import Message, MessageType, Metadata, _get_sqs_client
from hedwig.testing.factories import MetadataFactory


class TestMetadata:
    def test_new(self):
        data = MetadataFactory()
        metadata = Metadata(data)
        assert metadata.timestamp == data['timestamp']
        assert metadata.headers == data['headers']
        assert metadata.publisher == data['publisher']
        assert metadata.receipt is None

    def test_equal(self):
        metadata = Metadata(MetadataFactory())
        assert metadata == metadata

    def test_equal_fail(self):
        metadata = Metadata(MetadataFactory())
        assert metadata != metadata.as_dict()


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
            "schema": "https://hedwig.automatic.com/schema#/schemas/trip_created/1.0",
            "data": {
                "vehicle_id": 'C_1234567890123456',
                "user_id": 'U_1234567890123456',
            }
        }

        message = Message(message_data)
        assert message.id == message_data['id']
        assert message.metadata == Metadata(message_data['metadata'])
        assert message.headers == message_data['metadata']['headers']
        assert message.schema == 'https://hedwig.automatic.com/schema#/schemas/trip_created/1.0'
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

    def test_validate_invalid_schema(self, message):
        message._schema = 'foo'
        with pytest.raises(ValidationError):
            message.validate()

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

    def test_equal(self, message):
        assert message == message

    def test_equal_fail(self, message):
        assert message != message.as_dict()

    def test_getter_timestamp(self, message):
        assert message.timestamp == message.metadata.timestamp

    def test_getter_publisher(self, message):
        assert message.publisher == message.metadata.publisher


@mock.patch('hedwig.models.boto3.client')
def test_get_sqs_client(mock_boto3_client):
    client = _get_sqs_client()
    mock_boto3_client.assert_called_once_with(
        'sqs',
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY,
        aws_secret_access_key=settings.AWS_SECRET_KEY,
        aws_session_token=settings.AWS_SESSION_TOKEN,
        endpoint_url=settings.AWS_ENDPOINT_SQS,
    )
    assert client == mock_boto3_client.return_value
