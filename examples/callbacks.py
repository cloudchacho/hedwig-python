import logging
import time
from datetime import datetime, timezone

from hedwig.models import Message


def user_created_handler(message: Message) -> None:
    time.sleep(2)
    user_id = message.data["user_id"] if isinstance(message.data, dict) else message.data.user_id
    if user_id.endswith("0"):
        raise ValueError
    metadata = message.provider_metadata
    if hasattr(metadata, "publish_time"):
        publish_time = metadata.publish_time
        delivery_attempt = metadata.delivery_attempt
    elif hasattr(metadata, "sent_time"):
        publish_time = metadata.sent_time
        delivery_attempt = metadata.receive_count
    else:
        publish_time = datetime.fromtimestamp(0, timezone.utc)
        delivery_attempt = getattr(metadata, "delivery_attempt", None)
    now = datetime.now(timezone.utc)
    message_creation_time = datetime.fromtimestamp(message.timestamp / 1000, timezone.utc)
    latency_s = (now - publish_time).total_seconds()
    overall_latency_s = (now - message_creation_time).total_seconds()
    logging.info(
        f'Received user created message with id: {message.id} and data: {message.data}, '
        f'publish time: {publish_time}, message time: {message.timestamp}, delivery_attempt: {delivery_attempt} '
        f'transport latency seconds: {latency_s}, overall latency seconds: {overall_latency_s}'
    )
