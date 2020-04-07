import logging
from datetime import datetime, timezone

from hedwig.models import Message


def user_created_handler(message: Message) -> None:
    latency_s = (datetime.now(timezone.utc) - message.provider_metadata.publish_time).total_seconds()
    logging.info(
        f'Received user created message with id: {message.id} and data: {message.data}, '
        f'publish time: {message.provider_metadata.publish_time}, '
        f'latency seconds: {latency_s} delivery_attempt: {message.provider_metadata.delivery_attempt}'
    )
