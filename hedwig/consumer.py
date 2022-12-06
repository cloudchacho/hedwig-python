import threading
import typing
from typing import Optional

from hedwig.backends.utils import get_consumer_backend


def process_messages_for_lambda_consumer(lambda_event: dict) -> None:
    sns_consumer_backend = get_consumer_backend()
    sns_consumer_backend.process_messages(lambda_event)


def listen_for_messages(
    num_messages: int = 10,
    visibility_timeout_s: typing.Optional[int] = None,
    shutdown_event: Optional[threading.Event] = None,
) -> None:
    """
    Starts a Hedwig listener for message types provided and calls the callback handlers like so:

    .. code-block:: python

        callback_fn(message)

    The message is explicitly deleted only if callback function ran successfully. In case of an exception the message is
    kept on queue and processed again. If the callback keeps failing, the message is moved to the dead-letter queue.

    This function is blocking by default. It may be stopped by passing a shut down event object which can be set to
    stop the function.

    :param num_messages: Maximum number of messages to fetch in one API call. Defaults to 10
    :param visibility_timeout_s: The number of seconds the message should remain invisible to other queue readers.
        Defaults to None, which is queue default
    :param shutdown_event: An event to signal that the process should shut down. This prevents more messages from
        being de-queued and function exits after the current messages have been processed.
    """
    if not shutdown_event:
        shutdown_event = threading.Event()

    consumer_backend = get_consumer_backend()
    consumer_backend.fetch_and_process_messages(
        num_messages=num_messages, visibility_timeout=visibility_timeout_s, shutdown_event=shutdown_event
    )
