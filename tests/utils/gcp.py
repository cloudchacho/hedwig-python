from datetime import datetime, timezone
from time import time
from unittest import mock

from google.cloud.pubsub_v1.subscriber.message import Message as PubSubMessage
from google.pubsub_v1.types import ReceivedMessage


def build_gcp_queue_message(message):
    queue_message = mock.create_autospec(PubSubMessage, spec_set=True)
    payload, attrs = message.serialize()
    if isinstance(payload, str):
        payload = payload.encode('utf8')
        attrs['hedwig_encoding'] = 'utf8'
    queue_message.data, queue_message.attributes = payload, attrs
    queue_message.publish_time = datetime.now(timezone.utc)
    queue_message.delivery_attempt = 1
    return queue_message


def build_gcp_received_message(message):
    queue_message = mock.create_autospec(ReceivedMessage)
    queue_message.ack_id = "dummy_ack_id"
    payload, attrs = message.serialize()
    if isinstance(payload, str):
        payload = payload.encode('utf8')
        attrs['hedwig_encoding'] = 'utf8'
    queue_message.message = mock.create_autospec(PubSubMessage)
    queue_message.message.message_id = str(time())
    queue_message.message.data, queue_message.message.attributes = payload, attrs
    queue_message.message.publish_time = datetime.now(timezone.utc)
    queue_message.message.delivery_attempt = 1
    return queue_message
