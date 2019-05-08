from hedwig.backends.utils import get_consumer_backend


def requeue_dead_letter(num_messages: int = 10, visibility_timeout: int = None) -> None:
    """
    Re-queues everything in the Hedwig DLQ back into the Hedwig queue.

    :param num_messages: Maximum number of messages to fetch in one call. Defaults to 10.
    :param visibility_timeout: The number of seconds the message should remain invisible to other queue readers.
        Defaults to None, which is queue default
    """
    consumer_backend = get_consumer_backend(dlq=True)
    consumer_backend.requeue_dead_letter(num_messages, visibility_timeout)
