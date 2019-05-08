from hedwig.backends.base import HedwigPublisherBaseBackend
from hedwig.backends.utils import get_publisher_backend
from hedwig.models import Message


def publish(message: Message, backend: HedwigPublisherBaseBackend = None) -> None:
    """
    Publishes a message on Hedwig topic
    """
    backend = backend or get_publisher_backend()
    backend.publish(message)
