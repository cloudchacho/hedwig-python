import base64
import dataclasses
import threading
import uuid
from concurrent.futures import Future
from typing import Union, Dict, Optional, Generator, List
from urllib.parse import urlparse

import redis

from hedwig.backends.base import HedwigPublisherBaseBackend, HedwigConsumerBaseBackend
from hedwig.conf import settings
from hedwig.models import Message


def _client():
    uri = settings.REDIS_URI
    parsed = urlparse(uri)
    return redis.Redis(host=parsed.hostname, port=int(parsed.port), db=parsed.path.lstrip("/"), protocol=3)


@dataclasses.dataclass(frozen=True)
class RedisMetadata:
    id: str
    """
    Redis message id
    """

    stream: str
    """
    Redis stream name where message was consumed from
    """


class RedisStreamsPublisherBackend(HedwigPublisherBaseBackend):
    def __init__(self) -> None:
        self._r = _client()

    def _mock_queue_message(self, message: Message):
        raise NotImplementedError

    def _publish(self, message: Message, payload: Union[str, bytes], attributes: Dict[str, str]) -> Union[str, Future]:
        key = f"hedwig:{self.topic(message)}"
        # Redis requires UTF-8 encoded strings
        if isinstance(payload, bytes):
            payload = base64.encodebytes(payload).decode()
            attributes['hedwig_encoding'] = 'base64'
        message_id = self._r.xadd(key, {"hedwig_payload": payload, **attributes}, "*")
        return message_id


class RedisStreamsConsumerBackend(HedwigConsumerBaseBackend):
    def __init__(self, dlq=False) -> None:
        assert not dlq, "DLQ not supported at this time"
        self._r = _client()
        self._group = settings.HEDWIG_QUEUE
        self._consumer_id = str(uuid.uuid4())
        self._streams = [f"hedwig:{x}" for x in settings.HEDWIG_SUBSCRIPTIONS]
        super().__init__()

    def message_attributes(self, queue_message) -> dict:
        return {k.decode(): v.decode() for k, v in queue_message[2].items()}

    def extend_visibility_timeout(self, visibility_timeout_s: int, metadata) -> None:
        raise NotImplementedError

    def requeue_dead_letter(self, num_messages: int = 10, visibility_timeout: Optional[int] = None) -> None:
        raise NotImplementedError

    def pull_messages(
        self,
        num_messages: int = 10,
        visibility_timeout: Optional[int] = None,
        shutdown_event: Optional[threading.Event] = None,
    ) -> Union[Generator, List]:
        try:
            entries = self._r.xreadgroup(
                groupname=self._group,
                consumername=self._consumer_id,
                streams={x: ">" for x in self._streams},
                count=num_messages,
            )
            return [
                (stream, *message)
                for stream, stream_entries in entries.items()
                for message_list in stream_entries
                for message in message_list
            ]
        finally:
            self._perform_error_counter_inactivity_reset()
            self._call_heartbeat_hook()

    def process_message(self, queue_message) -> None:
        stream = queue_message[0].decode()
        message_id = queue_message[1].decode()
        fields = {k.decode(): v.decode() for k, v in queue_message[2].items()}
        # body is always UTF-8 string
        message_payload = fields.pop("hedwig_payload")
        if fields.pop("hedwig_encoding", None) == "base64":
            message_payload = base64.decodebytes(message_payload.encode())
        receipt = message_id
        self.message_handler(
            message_payload,
            fields,
            RedisMetadata(receipt, stream),
        )

    def ack_message(self, queue_message) -> None:
        stream = queue_message[0]
        message_id = queue_message[1]
        self._r.xack(stream, self._group, message_id)

    def nack_message(self, queue_message) -> None:
        raise NotImplementedError
