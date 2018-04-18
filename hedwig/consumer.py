import json
import logging
import typing

import boto3

from hedwig.conf import settings

try:
    from django import db
except ImportError:
    db = None

from hedwig.exceptions import RetryException, ValidationError
from hedwig.models import Message


WAIT_TIME_SECONDS = 20  # Maximum allowed by SQS

logger = logging.getLogger(__name__)


def _get_sqs_resource():
    return boto3.resource(
        'sqs',
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY,
        aws_secret_access_key=settings.AWS_SECRET_KEY,
        aws_session_token=settings.AWS_SESSION_TOKEN,
        endpoint_url=settings.AWS_ENDPOINT_SQS,
    )


def get_default_queue_name() -> str:
    return f'HEDWIG-{settings.HEDWIG_QUEUE}'


class LoggingError(Exception):
    """
    An exception that allows passing additional logging info.
    """
    def __init__(self, message, extra: dict = None):
        super(LoggingError, self).__init__(message)
        self.extra = extra


def log_received_message(message_body: dict) -> None:
    logger.debug('Received message', extra={
        'message_body': message_body,
    })


def log_invalid_message(message_json: str) -> None:
    logger.debug('Received invalid message', extra={
        'message_json': message_json,
    })


def _load_and_validate_message(data: dict) -> Message:
    message = Message(data)
    message.validate()
    message.validate_callback()

    return message


def message_handler(message_json: str, receipt: typing.Optional[str]) -> None:
    try:
        message_body = json.loads(message_json)
        settings.HEDWIG_POST_DESERIALIZE_HOOK(message_data=message_body)
        message = _load_and_validate_message(message_body)
    except (ValidationError, ValueError):
        log_invalid_message(message_json)
        raise

    log_received_message(message_body)

    if receipt is not None:
        message.metadata.receipt = receipt

    message.exec_callback()


def message_handler_sqs(queue_message) -> None:
    message_json = queue_message.body
    receipt = queue_message.receipt_handle

    message_handler(message_json, receipt)


def message_handler_lambda(lambda_record: dict) -> None:
    message_json = lambda_record['Sns']['Message']
    receipt = None

    message_handler(message_json, receipt)


def get_queue(queue_name: str):
    sqs = _get_sqs_resource()
    return sqs.get_queue_by_name(QueueName=queue_name)


def get_queue_messages(queue, num_messages: int, wait_timeout_s: typing.Optional[int] = None,
                       visibility_timeout: typing.Optional[int] = None) -> list:
    params = {
        'MaxNumberOfMessages': num_messages,
        'WaitTimeSeconds': wait_timeout_s or WAIT_TIME_SECONDS,
        'MessageAttributeNames': ['All'],
    }
    if visibility_timeout is not None:
        params['VisibilityTimeout'] = visibility_timeout
    return queue.receive_messages(**params)


def fetch_and_process_messages(queue_name: str, queue, num_messages: int = 1, visibility_timeout: int = None) -> None:

    for queue_message in get_queue_messages(queue, num_messages=num_messages, visibility_timeout=visibility_timeout):
        settings.HEDWIG_PRE_PROCESS_HOOK(sqs_queue_message=queue_message)

        try:
            message_handler_sqs(queue_message)
        except RetryException as e:
            # Retry without logging exception
            extra = (e.extra if isinstance(e, LoggingError) else None)
            logger.info('Retrying due to exception', extra=extra)
        except Exception as e:
            extra = (e.extra if isinstance(e, LoggingError) else None)
            logger.exception(f'Exception while processing message from {queue_name}', extra=extra)
        else:
            try:
                queue_message.delete()
            except Exception:
                logger.exception(f'Exception while deleting message from {queue_name}')


def process_messages_for_lambda_consumer(lambda_event: dict) -> None:
    for record in lambda_event['Records']:
        settings.HEDWIG_PRE_PROCESS_HOOK(sns_record=record)

        try:
            message_handler_lambda(record)
        except Exception as e:
            extra = (e.extra if isinstance(e, LoggingError) else None)
            logger.exception('Exception while processing message', extra=extra)
            # let it bubble up so message ends up in DLQ
            raise


def listen_for_messages(
        num_messages: int = 10, visibility_timeout_s: typing.Optional[int] = None,
        loop_count: typing.Optional[int] = None) -> None:
    """
    Starts a Hedwig listener for message types provided and calls the callback handlers like so:

    callback_fn(message).

    The message is explicitly deleted only if callback function ran successfully. In case of an exception the message is
    kept on queue and processed again. If the callback keeps failing, SQS dead letter queue mechanism kicks in and
    the message is moved to the dead-letter queue.

    :param num_messages: Maximum number of messages to fetch in one SQS API call. Defaults to 10
    :param visibility_timeout_s: The number of seconds the message should remain invisible to other queue readers.
        Defaults to None, which is queue default
    :param loop_count: How many times to fetch messages from SQS. Default to None, which means loop forever.
    """
    queue_name = get_default_queue_name()

    queue = get_queue(queue_name)
    if loop_count is None:
        while True:
            fetch_and_process_messages(
                queue_name, queue, num_messages=num_messages, visibility_timeout=visibility_timeout_s)
    else:
        for _ in range(loop_count):
            fetch_and_process_messages(
                queue_name, queue, num_messages=num_messages, visibility_timeout=visibility_timeout_s)
