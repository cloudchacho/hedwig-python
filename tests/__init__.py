import threading
from concurrent.futures import Future
from typing import Union, Dict, Optional, Generator, List

from hedwig.backends.base import HedwigPublisherBaseBackend, HedwigConsumerBaseBackend
from hedwig.models import Message


class MockHedwigPublisherBackend(HedwigPublisherBaseBackend):
    def _mock_queue_message(self, message: Message):
        pass

    def _publish(self, message: Message, payload: Union[str, bytes], attributes: Dict[str, str]) -> Union[str, Future]:
        pass


class MockHedwigConsumerBackend(HedwigConsumerBaseBackend):
    def message_attributes(self, queue_message) -> dict:
        pass

    def extend_visibility_timeout(self, visibility_timeout_s: int, metadata) -> None:
        pass

    def requeue_dead_letter(self, num_messages: int = 10, visibility_timeout: Optional[int] = None) -> None:
        pass

    def pull_messages(
        self,
        num_messages: int = 10,
        visibility_timeout: Optional[int] = None,
        shutdown_event: Optional[threading.Event] = None,
    ) -> Union[Generator, List]:
        pass

    def process_message(self, queue_message) -> None:
        pass

    def ack_message(self, queue_message) -> None:
        pass

    def nack_message(self, queue_message) -> None:
        pass
