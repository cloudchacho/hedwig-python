import base64
import dataclasses
import threading
import uuid
from concurrent.futures import Future
from typing import Union, Dict, Optional, Generator, List, Tuple

from redis import Redis

from hedwig.backends.base import HedwigPublisherBaseBackend, HedwigConsumerBaseBackend
from hedwig.conf import settings
from hedwig.models import Message


def _client():
    return Redis.from_url(settings.REDIS_URL, protocol=3)


@dataclasses.dataclass(frozen=True)
class RedisMessage:
    stream: bytes
    key: bytes
    payload: dict[bytes, bytes]
    delivery_attempt: int


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

    delivery_attempt: int
    """
    The delivery attempt counter.
    The first delivery of a given message will have this value as 1. The value
    is calculated as best effort and is approximate.
    """


class RedisStreamsPublisherBackend(HedwigPublisherBaseBackend):
    def __init__(self) -> None:
        self._r = _client()

    def _mock_queue_message(self, message: Message) -> RedisMessage:
        payload, attributes = message.serialize()
        if isinstance(payload, bytes):
            payload = base64.encodebytes(payload).decode()
            attributes['hedwig_encoding'] = 'base64'
        redis_message = {"hedwig_payload": payload, **attributes}
        redis_message = {k.encode(): v.encode() for k, v in redis_message.items()}
        stream = f"hedwig:{self.topic(message)}".encode()
        message_id = f"{attributes['hedwig_message_timestamp']}-0".encode()
        return RedisMessage(stream=stream, key=message_id, payload=redis_message, delivery_attempt=1)

    def _publish(self, message: Message, payload: Union[str, bytes], attributes: Dict[str, str]) -> Union[str, Future]:
        key = f"hedwig:{self.topic(message)}"
        # Redis requires UTF-8 encoded strings
        if isinstance(payload, bytes):
            payload = base64.encodebytes(payload).decode()
            attributes['hedwig_encoding'] = 'base64'
        redis_message = {"hedwig_payload": payload, **attributes}
        message_id = self._r.xadd(key, redis_message)
        return message_id


class RedisStreamsConsumerBackend(HedwigConsumerBaseBackend):
    def __init__(self, dlq=False) -> None:
        assert (
            settings.HEDWIG_MAX_DELIVERY_ATTEMPTS
        ), "HEDWIG_MAX_DELIVERY_ATTEMPTS must be set for RedisStreamsConsumerBackend"
        assert (
            settings.HEDWIG_VISIBILITY_TIMEOUT_S
        ), "HEDWIG_VISIBILITY_TIMEOUT_S must be set for RedisStreamsConsumerBackend"
        self._r = _client()
        self._group = settings.HEDWIG_QUEUE
        self._consumer_id = str(uuid.uuid4())
        self._main_stream = f"hedwig:{settings.HEDWIG_QUEUE}"
        self._deadletter_stream = f"hedwig:{settings.HEDWIG_QUEUE}:dlq"
        if dlq:
            self._streams = [self._deadletter_stream]
        else:
            self._streams = [f"hedwig:{x}" for x in settings.HEDWIG_SUBSCRIPTIONS]
            # main queue for DLQ re-queued messages
            self._streams.append(self._main_stream)
        super().__init__()

    def message_attributes(self, queue_message: RedisMessage) -> dict:
        return {k.decode(): v.decode() for k, v in queue_message.payload.items()}

    def extend_visibility_timeout(self, visibility_timeout_s: int, metadata) -> None:
        assert visibility_timeout_s == settings.HEDWIG_VISIBILITY_TIMEOUT_S, "Visibility timeout is not configurable"
        # reset idle time to 0, thereby extending visibility timeout
        self._r.xclaim(
            name=metadata.stream,
            groupname=self._group,
            consumername=self._consumer_id,
            min_idle_time=0,
            message_ids=[metadata.id],
            justid=True,
        )

    def requeue_dead_letter(self, num_messages: int = 10, visibility_timeout: Optional[int] = None) -> None:
        total_count = 0
        while True:
            dlq_entries: Tuple[str, List[Tuple[str, Dict]], List] = self._r.xautoclaim(
                name=self._deadletter_stream,
                groupname=self._group,
                consumername=self._consumer_id,
                min_idle_time=0,
                start_id="0-0",
                count=num_messages,
            )
            if not dlq_entries:
                break
            count = 0
            messages = dlq_entries[1]
            if not messages:
                break

            count += len(messages)
            total_count += count
            self._requeue_messages(messages)
            print(f"Requeued {count} messages")
        while True:
            entries: Dict[str, List[List[Tuple[str, Dict]]]] = self._r.xreadgroup(
                self._group,
                self._consumer_id,
                streams={self._deadletter_stream: ">"},
                count=num_messages,
                block=500,
            )
            if not entries:
                break

            messages = []
            for stream, stream_entries in entries.items():
                for msgs in stream_entries:
                    if not msgs:
                        continue
                    messages.extend(msgs)

            count = len(messages)
            total_count += count
            if count == 0:
                break
            self._requeue_messages(messages)
            print(f"Requeued {count} messages")

        print('-' * 80)
        print(f"Requeued total {total_count} messages")

    def _requeue_messages(self, messages):
        with self._r.pipeline() as pipeline:
            message_ids = []
            for message in messages:
                message_ids.append(message[0])
                pipeline.xadd(self._main_stream, message[1])
            pipeline.xack(self._deadletter_stream, self._group, *message_ids)
            pipeline.execute()

    def _process_raw_messages(
        self, stream: bytes, messages: list[tuple[bytes, dict[bytes, bytes]]]
    ) -> Generator[RedisMessage, None, None]:
        for message in messages:
            message_id, message_payload = message
            # manual tracking of delivery attempts
            metadata = self._r.xpending_range(stream, self._group, message_id, message_id, 1)[0]
            if metadata["times_delivered"] > settings.HEDWIG_MAX_DELIVERY_ATTEMPTS:
                with self._r.pipeline() as pipeline:
                    pipeline.xadd(self._deadletter_stream, message_payload)
                    pipeline.xack(stream, self._group, message_id)
                    pipeline.execute()
                continue
            yield RedisMessage(
                stream=stream,
                key=message_id,
                payload=message_payload,
                delivery_attempt=metadata["times_delivered"],
            )

    def pull_messages(  # type: ignore[return]
        self,
        num_messages: int = 10,
        visibility_timeout: Optional[int] = None,
        shutdown_event: Optional[threading.Event] = None,
    ) -> Union[Generator, List]:
        assert not visibility_timeout, "Visibility timeout is not configurable"
        try:
            # claim timed out messages
            for stream in self._streams:
                stream_entries = self._r.xautoclaim(
                    name=stream,
                    groupname=self._group,
                    consumername=self._consumer_id,
                    min_idle_time=int(settings.HEDWIG_VISIBILITY_TIMEOUT_S * 1000),
                    start_id="0-0",
                    count=num_messages,
                )[1]
                yield from self._process_raw_messages(stream.encode(), stream_entries)
            entries: dict[bytes, list[list[tuple[bytes, dict[bytes, bytes]]]]] = self._r.xreadgroup(
                groupname=self._group,
                consumername=self._consumer_id,
                streams={x: ">" for x in self._streams},
                count=num_messages,
                block=500,
            )
            if not entries:
                return []
            for stream_, stream_entries in entries.items():
                for messages in stream_entries:
                    yield from self._process_raw_messages(stream_, messages)
        finally:
            self._perform_error_counter_inactivity_reset()
            self._call_heartbeat_hook()

    def process_message(self, queue_message: RedisMessage) -> None:
        stream = queue_message.stream.decode()
        message_id = queue_message.key.decode()
        fields = self.message_attributes(queue_message)
        # body is always UTF-8 string
        message_payload = fields.pop("hedwig_payload")
        if fields.pop("hedwig_encoding", None) == "base64":
            message_payload = base64.decodebytes(message_payload.encode())
        self.message_handler(
            message_payload,
            fields,
            RedisMetadata(message_id, stream, queue_message.delivery_attempt),
        )

    def ack_message(self, queue_message: RedisMessage) -> None:
        self._r.xack(queue_message.stream, self._group, queue_message.key)

    def nack_message(self, queue_message: RedisMessage) -> None:
        # let visibility timeout take care of it
        pass
