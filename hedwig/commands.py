import json
import logging

import funcy

from hedwig.consumer import get_default_queue_name, get_queue, get_queue_messages


class PartialFailure(Exception):
    """
    Error indicating either send_messages or delete_messages API call failed partially
    """
    def __init__(self, result):
        self.success_count = len(result['Successful'])
        self.failure_count = len(result['Failed'])
        self.result = result


def _enqueue_messages(queue, queue_messages, delay_seconds: int=None) -> None:
    params = {}

    if delay_seconds:
        assert isinstance(delay_seconds, int)
        params["DelaySeconds"] = delay_seconds

    result = queue.send_messages(
        Entries=[
            funcy.merge(
                {
                    'Id': queue_message.message_id,
                    'MessageBody': queue_message.body,
                },
                {
                    'MessageAttributes': queue_message.message_attributes
                } if queue_message.message_attributes else {},
                params
            )
            for queue_message in queue_messages
        ]
    )
    if result.get('Failed'):
        raise PartialFailure(result)


def get_dead_letter_queue(queue):
    queue_name = json.loads(queue.attributes['RedrivePolicy'])['deadLetterTargetArn'].split(':')[-1]
    return get_queue(queue_name)


def requeue_dead_letter(num_messages: int=10, visibility_timeout: int=None) -> None:
    """
    Re-queues everything in the Hedwig DLQ back into the Hedwig queue.

    :param num_messages: Maximum number of messages to fetch in one SQS call. Defaults to 10.
    :param visibility_timeout: The number of seconds the message should remain invisible to other queue readers.
        Defaults to None, which is queue default
    """
    queue = get_queue(get_default_queue_name())

    dead_letter_queue = get_dead_letter_queue(queue)

    logging.info("Re-queueing messages from {} to {}".format(dead_letter_queue.url, queue.url))
    while True:
        queue_messages = get_queue_messages(
            dead_letter_queue, num_messages=num_messages, visibility_timeout=visibility_timeout, wait_timeout_s=1,
        )
        if not queue_messages:
            break

        logging.info("got {} messages from dlq".format(len(queue_messages)))

        _enqueue_messages(queue, queue_messages)
        dead_letter_queue.delete_messages(
            Entries=[
                {
                    'Id': message.message_id,
                    'ReceiptHandle': message.receipt_handle
                }
                for message in queue_messages
            ]
        )

        logging.info("Re-queued {} messages".format(len(queue_messages)))
