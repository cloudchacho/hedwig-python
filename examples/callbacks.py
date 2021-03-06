import logging
from datetime import datetime, timezone

from hedwig.backends.gcp import GoogleMetadata
from hedwig.models import Message


def user_created_handler(message: Message) -> None:
    if isinstance(message.provider_metadata, GoogleMetadata):
        publish_time = message.provider_metadata.publish_time
        delivery_attempt = message.provider_metadata.delivery_attempt
    else:
        publish_time = message.provider_metadata.sent_time
        delivery_attempt = message.provider_metadata.receive_count
    now = datetime.now(timezone.utc)
    message_creation_time = datetime.fromtimestamp(message.timestamp / 1000, timezone.utc)
    latency_s = (now - publish_time).total_seconds()
    overall_latency_s = (now - message_creation_time).total_seconds()
    logging.info(
        f'Received user created message with id: {message.id} and data: {message.data}, '
        f'publish time: {publish_time}, message time: {message.timestamp}, delivery_attempt: {delivery_attempt} '
        f'transport latency seconds: {latency_s}, overall latency seconds: {overall_latency_s}'
    )
