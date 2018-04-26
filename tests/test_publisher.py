import copy
from decimal import Decimal
import json
from unittest import mock
import uuid

import pytest

from hedwig.conf import settings
from hedwig.models import Message, MessageType
from hedwig.exceptions import ValidationError, CallbackNotFound
from hedwig.publisher import publish, _get_sns_topic, _convert_to_json, _publish_over_sns
from hedwig.testing.factories import MessageFactory


def test__get_sns_topic(message):
    message.validate()
    assert _get_sns_topic(message) == f'arn:aws:sns:{settings.AWS_REGION}:{settings.AWS_ACCOUNT_ID}:hedwig-' \
                                      f'{message.topic}'


@mock.patch('hedwig.publisher._get_sns_client', autospec=True)
def test__publish_over_sns(mock_get_sns_client, message):
    message.validate()
    topic = _get_sns_topic(message)
    message_json = _convert_to_json(message.as_dict())

    _publish_over_sns(topic, message_json, message.headers)

    mock_get_sns_client.assert_called_once_with()
    mock_get_sns_client.return_value.publish.assert_called_once_with(
        TopicArn=topic,
        Message=message_json,
        MessageAttributes={
            k: {
                'DataType': 'String',
                'StringValue': str(v),
            } for k, v in message.headers.items()
        },
    )


@pytest.fixture(name='message_with_decimal')
def _message_with_decimal(message_data):
    message_data = copy.deepcopy(message_data)
    message_data['data']['user_id'] = Decimal(1469056316326)
    return Message(message_data)


def test__convert_to_json_decimal(message_with_decimal):
    assert json.loads(_convert_to_json(message_with_decimal.as_dict()))['data']['user_id'] == \
        float(message_with_decimal.data['user_id'])


@mock.patch('hedwig.publisher._convert_to_json', autospec=True)
@mock.patch('hedwig.publisher._publish_over_sns', autospec=True)
def test_publish(mock_publish_over_sns, mock_convert_to_json, message):
    message.validate()

    sns_id = str(uuid.uuid4())

    mock_publish_over_sns.return_value = {'MessageId': sns_id}

    publish(message)

    topic = _get_sns_topic(message)
    mock_publish_over_sns.assert_called_once_with(
        topic,
        mock_convert_to_json.return_value,
        message.headers
    )
    mock_convert_to_json.assert_called_once_with(message.as_dict())


default_headers_hook = mock.MagicMock()


@mock.patch('hedwig.publisher._convert_to_json', autospec=True)
@mock.patch('hedwig.publisher._publish_over_sns', autospec=True)
def test_default_headers_hook(mock_publish_over_sns, mock_convert_to_json, message, settings):
    settings.HEDWIG_DEFAULT_HEADERS = 'tests.test_publisher.default_headers_hook'
    default_headers_hook.return_value = {
        'mickey': 'mouse',
    }

    message.validate()

    sns_id = str(uuid.uuid4())

    mock_publish_over_sns.return_value = {'MessageId': sns_id}

    publish(message)

    topic = _get_sns_topic(message)
    mock_publish_over_sns.assert_called_once_with(
        topic,
        mock_convert_to_json.return_value,
        {**message.headers, **default_headers_hook.return_value},
    )
    expected = message.as_dict()
    expected['metadata']['headers'].update(default_headers_hook.return_value)
    mock_convert_to_json.assert_called_once_with(expected)

    default_headers_hook.assert_called_once_with(message=message)


def pre_serialize_hook(message_data):
    # clear headers to make sure we are not able to destroy sqs
    # message attributes
    message_data['metadata']['headers'].clear()


@mock.patch('hedwig.publisher._convert_to_json', autospec=True)
@mock.patch('hedwig.publisher._publish_over_sns', autospec=True)
def test_pre_serialize_hook(mock_publish_over_sns, mock_convert_to_json, message, settings):
    settings.HEDWIG_PRE_SERIALIZE_HOOK = 'tests.test_publisher.pre_serialize_hook'

    message.validate()

    sns_id = str(uuid.uuid4())

    mock_publish_over_sns.return_value = {'MessageId': sns_id}

    publish(message)

    topic = _get_sns_topic(message)
    mock_publish_over_sns.assert_called_once_with(
        topic,
        mock_convert_to_json.return_value,
        message.headers
    )
    message_data = message.as_dict()
    message_data['metadata']['headers'].clear()
    mock_convert_to_json.assert_called_once_with(message_data)


@mock.patch('tests.handlers._trip_created_handler', autospec=True)
def test_sync_mode(callback_mock, message, settings):
    settings.HEDWIG_SYNC = True

    message.publish()
    callback_mock.assert_called_once_with(message)


def test_sync_mode_detects_invalid_callback(settings):
    settings.HEDWIG_SYNC = True

    message = MessageFactory(msg_type=MessageType.vehicle_created)
    with pytest.raises(ValidationError) as exc_info:
        message.publish()
    assert isinstance(exc_info.value.__context__, CallbackNotFound)
