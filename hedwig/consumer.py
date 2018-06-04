import json
import itertools
import logging
import threading
import typing

import boto3

from hedwig.conf import settings
from hedwig.exceptions import RetryException, IgnoreException, ValidationError, LoggingException
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

    try:
        message.exec_callback()
    except IgnoreException:
        logger.info(f'Ignoring task {message.id}')
        return
    except LoggingException as e:
        # log with message and extra
        logger.exception(str(e), extra=e.extra)
        # let it bubble up so message ends up in DLQ
        raise
    except RetryException:
        # Retry without logging exception
        logger.info('Retrying due to exception')
        # let it bubble up so message ends up in DLQ
        raise
    except Exception:
        logger.exception(f'Exception while processing message')
        # let it bubble up so message ends up in DLQ
        raise


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


def fetch_and_process_messages(
        queue_name: str, queue, num_messages: int = 1, visibility_timeout: typing.Optional[int] = None) -> None:

    for queue_message in get_queue_messages(queue, num_messages=num_messages, visibility_timeout=visibility_timeout):
        settings.HEDWIG_PRE_PROCESS_HOOK(sqs_queue_message=queue_message)

        try:
            message_handler_sqs(queue_message)
            try:
                queue_message.delete()
            except Exception:
                logger.exception(f'Exception while deleting message from {queue_name}')
        except Exception:
            # already logged in message_handler
            pass


def process_messages_for_lambda_consumer(lambda_event: dict) -> None:
    for record in lambda_event['Records']:
        settings.HEDWIG_PRE_PROCESS_HOOK(sns_record=record)

        message_handler_lambda(record)


def listen_for_messages(
        num_messages: int = 10, visibility_timeout_s: typing.Optional[int] = None,
        loop_count: typing.Optional[int] = None, shutdown_event: threading.Event = None) -> None:
    """
    Starts a Hedwig listener for message types provided and calls the callback handlers like so:

    callback_fn(message).

    The message is explicitly deleted only if callback function ran successfully. In case of an exception the message is
    kept on queue and processed again. If the callback keeps failing, SQS dead letter queue mechanism kicks in and
    the message is moved to the dead-letter queue.

    This function is blocking by default. It may be run for specific number of loops by passing `loop_count`. It may
    also be stopped by passing a shut down event object which can be set to stop the function.

    :param num_messages: Maximum number of messages to fetch in one SQS API call. Defaults to 10
    :param visibility_timeout_s: The number of seconds the message should remain invisible to other queue readers.
        Defaults to None, which is queue default
    :param loop_count: How many times to fetch messages from SQS. Default to None, which means loop forever.
    :param shutdown_event: An event to signal that the process should shut down. This prevents more messages from
        being de-queued and function exits after the current messages have been processed.
    """
    if not shutdown_event:
        shutdown_event = threading.Event()

    queue_name = get_default_queue_name()

    queue = get_queue(queue_name)
    for count in itertools.count():
        if (loop_count is None or count < loop_count) and not shutdown_event.is_set():
            fetch_and_process_messages(
                queue_name, queue, num_messages=num_messages, visibility_timeout=visibility_timeout_s)
        else:
            break
