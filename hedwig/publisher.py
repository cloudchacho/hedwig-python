import typing
from concurrent.futures import Future
from typing import Optional

from hedwig.backends.base import HedwigPublisherBaseBackend
from hedwig.backends.utils import get_publisher_backend
from hedwig.models import Message


def publish(message: Message, backend: Optional[HedwigPublisherBaseBackend] = None) -> typing.Union[str, Future]:
    """
    Publishes a message on Hedwig topic
    :returns: for async publishers, returns a future that represents the publish api call, otherwise, returns
    the published message id
    """
    backend = backend or get_publisher_backend()
    return backend.publish(message)
