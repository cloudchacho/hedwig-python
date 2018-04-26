import json
import logging
import copy
from decimal import Decimal
from unittest import mock

import boto3
from botocore.config import Config
from retrying import retry

from hedwig import Message
from hedwig.conf import settings


log = logging.getLogger(__name__)


def _get_sns_client():
    # https://botocore.readthedocs.io/en/stable/reference/config.html
    # seconds
    config = Config(
        connect_timeout=settings.AWS_CONNECT_TIMEOUT_S,
        read_timeout=settings.AWS_READ_TIMEOUT_S,
    )

    return boto3.client(
        'sns',
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY,
        aws_secret_access_key=settings.AWS_SECRET_KEY,
        aws_session_token=settings.AWS_SESSION_TOKEN,
        endpoint_url=settings.AWS_ENDPOINT_SNS,
        config=config,
    )


def _get_sns_topic(message: Message) -> str:
    return f'arn:aws:sns:{settings.AWS_REGION}:{settings.AWS_ACCOUNT_ID}:hedwig-{message.topic}'


@retry(stop_max_attempt_number=3, stop_max_delay=3000)
def _publish_over_sns(topic: str, message_json: str, message_attributes: dict) -> dict:
    # transform (http://boto.cloudhackers.com/en/latest/ref/sns.html#boto.sns.SNSConnection.publish)
    message_attributes = {
        k: {
            'DataType': 'String',
            'StringValue': str(v),
        } for k, v in message_attributes.items()
    }
    client = _get_sns_client()
    response = client.publish(
        TopicArn=topic,
        Message=message_json,
        MessageAttributes=message_attributes,
    )
    return response


def _log_published_message(message_body: dict, message_id: str) -> None:
    log.debug('Sent message', extra={'message_body': message_body, 'message_id': message_id})


def _decimal_json_default(obj):
    if isinstance(obj, Decimal):
        int_val = int(obj)
        if int_val == obj:
            return int_val
        else:
            return float(obj)
    raise TypeError


def _convert_to_json(data: dict) -> str:
    return json.dumps(data, default=_decimal_json_default)


def dispatch_mock_sqs_message(message: Message):
    from hedwig import consumer

    sqs_message = mock.Mock()
    sqs_message.body = json.dumps(message.as_dict())
    sqs_message.receipt_handle = 'test-receipt'
    settings.HEDWIG_PRE_PROCESS_HOOK(sqs_queue_message=sqs_message)
    consumer.message_handler_sqs(sqs_message)


def publish(message: Message) -> None:
    """
    Publishes a message on Hedwig topic
    """
    if not message.type:
        message.validate()

    if settings.HEDWIG_SYNC:
        dispatch_mock_sqs_message(message)
        return

    message_body = message.as_dict()

    headers = {
        **settings.HEDWIG_DEFAULT_HEADERS(message=message), **message_body['metadata']['headers']
    }
    # make a copy to prevent changing "headers" variable contents in
    # pre serialize hook
    message_body['metadata']['headers'] = copy.deepcopy(headers)
    settings.HEDWIG_PRE_SERIALIZE_HOOK(message_data=message_body)
    payload = _convert_to_json(message_body)

    topic = _get_sns_topic(message)
    response = _publish_over_sns(topic, payload, headers)

    _log_published_message(message_body, response['MessageId'])
