import logging

from hedwig.models import Message


def user_created_handler(message: Message) -> None:
    logging.info(
        f'Received user created message with id: {message.id} and data: {message.data}, '
        f'publish time: {message.provider_metadata.publish_time}'
    )
