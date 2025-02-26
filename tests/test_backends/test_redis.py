import base64
import threading
from time import sleep
from unittest import mock

import freezegun
import pytest

from hedwig.commands import requeue_dead_letter
from hedwig.models import Message

try:
    from hedwig.backends.redis import RedisMetadata, RedisMessage
except ImportError:
    pass
from hedwig.exceptions import ValidationError, CallbackNotFound
from tests.models import MessageType

redis = pytest.importorskip('hedwig.backends.redis')


@pytest.fixture(autouse=True)
def redis_settings(settings):
    settings.REDIS_URL = "redis://redis:6379/10"
    settings.HEDWIG_PUBLISHER_BACKEND = "hedwig.backends.redis.RedisStreamsPublisherBackend"
    settings.HEDWIG_CONSUMER_BACKEND = "hedwig.backends.redis.RedisStreamsConsumerBackend"
    settings.HEDWIG_VISIBILITY_TIMEOUT_S = 10
    settings.HEDWIG_MAX_DELIVERY_ATTEMPTS = 1
    settings.HEDWIG_QUEUE = "dev:myapp"
    settings.HEDWIG_SUBSCRIPTIONS = ['dev-trip-created-v1']
    yield settings


@pytest.fixture
def redis_client():
    return redis._client()


@pytest.fixture(autouse=True)
def setup_redis_stream_groups(redis_client, redis_settings):
    for hedwig_subscription in redis_settings.HEDWIG_SUBSCRIPTIONS:
        redis_client.xgroup_create(
            name=f"hedwig:{hedwig_subscription}",
            groupname=redis_settings.HEDWIG_QUEUE,
            mkstream=True,
        )
    redis_client.xgroup_create(
        name=f"hedwig:{redis_settings.HEDWIG_QUEUE}",
        groupname=redis_settings.HEDWIG_QUEUE,
        mkstream=True,
    )
    redis_client.xgroup_create(
        name=f"hedwig:{redis_settings.HEDWIG_QUEUE}:dlq",
        groupname=redis_settings.HEDWIG_QUEUE,
        mkstream=True,
    )
    yield
    for hedwig_subscription in redis_settings.HEDWIG_SUBSCRIPTIONS:
        redis_client.xgroup_destroy(
            name=f"hedwig:{hedwig_subscription}",
            groupname=redis_settings.HEDWIG_QUEUE,
        )
        redis_client.delete(f"hedwig:{hedwig_subscription}")
    redis_client.xgroup_destroy(
        name=f"hedwig:{redis_settings.HEDWIG_QUEUE}",
        groupname=redis_settings.HEDWIG_QUEUE,
    )
    redis_client.delete(f"hedwig:{redis_settings.HEDWIG_QUEUE}")
    redis_client.xgroup_destroy(
        name=f"hedwig:{redis_settings.HEDWIG_QUEUE}:dlq",
        groupname=redis_settings.HEDWIG_QUEUE,
    )
    redis_client.delete(f"hedwig:{redis_settings.HEDWIG_QUEUE}:dlq")


def assert_redis_message_payload(message: Message, redis_message_payload: dict[bytes, bytes]):
    expected_hedwig_payload, expected_attributes = message.serialize()
    # convert bytes to strings
    attributes = {k.decode(): v.decode() for k, v in redis_message_payload.items()}
    hedwig_payload = attributes.pop("hedwig_payload")
    if attributes.pop("hedwig_encoding", None) == "base64":
        hedwig_payload = base64.decodebytes(hedwig_payload.encode())
    assert attributes == expected_attributes
    assert hedwig_payload == expected_hedwig_payload


@freezegun.freeze_time("2025-02-18")
class TestPubSubPublisher:
    def test_publish_success(self, message, redis_client):
        redis_publisher = redis.RedisStreamsPublisherBackend()
        message_id = redis_publisher.publish(message)

        stream = f"hedwig:{redis_publisher.topic(message)}".encode()
        resp = redis_client.xread(streams={stream: "0-0"})
        assert len(resp) == 1
        assert stream in resp
        messages = resp[stream]
        assert len(messages) == 1
        msg_id, msg_payload = messages[0][0]
        assert msg_id == message_id
        assert_redis_message_payload(message, msg_payload)

    @mock.patch('tests.handlers._trip_created_handler', autospec=True)
    def test_sync_mode(self, callback_mock, message_factory, redis_settings):
        redis_settings.HEDWIG_SYNC = True
        publisher = redis.RedisStreamsPublisherBackend()
        message = message_factory(msg_type=MessageType.trip_created)
        stream = f"hedwig:{publisher.topic(message)}"
        message_id = "1739836800000-0"

        message.publish()
        callback_mock.assert_called_once_with(
            message.with_provider_metadata(RedisMetadata(id=message_id, stream=stream, delivery_attempt=1))
        )

    def test_sync_mode_detects_invalid_callback(self, redis_settings, message_factory):
        redis_settings.HEDWIG_SYNC = True

        message = message_factory(msg_type=MessageType.vehicle_created)
        with pytest.raises(ValidationError) as exc_info:
            message.publish()
        assert isinstance(exc_info.value.__context__, CallbackNotFound)


pre_process_hook = mock.MagicMock()
post_process_hook = mock.MagicMock()
heartbeat_hook = mock.MagicMock()


@pytest.fixture(name='prepost_process_hooks')
def _prepost_process_hooks(redis_settings):
    redis_settings.HEDWIG_HEARTBEAT_HOOK = 'tests.test_backends.test_redis.heartbeat_hook'
    redis_settings.HEDWIG_PRE_PROCESS_HOOK = 'tests.test_backends.test_redis.pre_process_hook'
    redis_settings.HEDWIG_POST_PROCESS_HOOK = 'tests.test_backends.test_redis.post_process_hook'
    yield
    pre_process_hook.reset_mock(side_effect=True)
    post_process_hook.reset_mock(side_effect=True)
    heartbeat_hook.reset_mock(side_effect=True)


def _shutdown(fn):
    """
    decorator for pull_messages() method to set shutdown event
    and break from the infinite loop in fetch_and_process_messages
    """

    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        finally:
            kwargs["shutdown_event"].set()

    return wrapper


def _publish_and_consume_message(message: Message):
    msg_id = message.publish()
    shutdown_event = threading.Event()
    redis_consumer = redis.RedisStreamsConsumerBackend()
    redis_consumer.pull_messages = _shutdown(redis_consumer.pull_messages)
    redis_consumer.fetch_and_process_messages(num_messages=1, shutdown_event=shutdown_event)
    return msg_id


class TestRedisConsumer:
    def test_pull_messages(self, message, prepost_process_hooks):
        message_id = message.publish()

        redis_consumer = redis.RedisStreamsConsumerBackend()
        items = list(redis_consumer.pull_messages(num_messages=1))

        assert len(items) == 1
        redis_message: RedisMessage = items[0]
        assert redis_message.stream == b'hedwig:dev-trip-created-v1'
        assert redis_message.key == message_id
        assert_redis_message_payload(message, redis_message.payload)
        assert redis_message.delivery_attempt == 1
        heartbeat_hook.assert_called_once_with(error_count=0)

        # assert there is no available messages since above message is currently in PEL (Pending Entries List)
        items = list(redis_consumer.pull_messages(num_messages=1))
        assert len(items) == 0

    def test_pull_messages_with_expired_visibility_timeout(self, message, prepost_process_hooks, redis_settings):
        redis_settings.HEDWIG_VISIBILITY_TIMEOUT_S = 0.3
        redis_settings.HEDWIG_MAX_DELIVERY_ATTEMPTS = 3
        message_id = message.publish()

        redis_consumer = redis.RedisStreamsConsumerBackend()
        items = list(redis_consumer.pull_messages(num_messages=1))

        assert len(items) == 1
        redis_message: RedisMessage = items[0]
        assert redis_message.stream == b'hedwig:dev-trip-created-v1'
        assert redis_message.key == message_id
        assert_redis_message_payload(message, redis_message.payload)
        assert redis_message.delivery_attempt == 1
        heartbeat_hook.assert_called_once_with(error_count=0)

        sleep(0.5)
        heartbeat_hook.reset_mock()
        # create new consumer and auto-claim message, which visibility timeout was expired
        redis_consumer = redis.RedisStreamsConsumerBackend()
        items = list(redis_consumer.pull_messages(num_messages=1))

        assert len(items) == 1
        redis_message = items[0]
        assert redis_message.stream == b'hedwig:dev-trip-created-v1'
        assert redis_message.key == message_id
        assert_redis_message_payload(message, redis_message.payload)
        assert redis_message.delivery_attempt == 2
        heartbeat_hook.assert_called_once_with(error_count=0)

    def test_pull_messages_and_move_to_dlq(self, message, prepost_process_hooks, redis_settings, redis_client):
        redis_settings.HEDWIG_VISIBILITY_TIMEOUT_S = 0.3
        # 2nd delivery attempt will be moved to dlq
        redis_settings.HEDWIG_MAX_DELIVERY_ATTEMPTS = 1
        message_id = message.publish()

        redis_consumer = redis.RedisStreamsConsumerBackend()
        items = list(redis_consumer.pull_messages(num_messages=1))

        assert len(items) == 1
        redis_message: RedisMessage = items[0]
        assert redis_message.stream == b'hedwig:dev-trip-created-v1'
        assert redis_message.key == message_id
        assert_redis_message_payload(message, redis_message.payload)
        assert redis_message.delivery_attempt == 1
        heartbeat_hook.assert_called_once_with(error_count=0)

        sleep(0.5)
        heartbeat_hook.reset_mock()
        # because max delivery attempt is set to 1, 2nd attempt will move message to dlq
        items = list(redis_consumer.pull_messages(num_messages=1))
        assert len(items) == 0

        # validate message exists in dlq and matches original message
        dlq_stream = redis_consumer._deadletter_stream.encode()
        entries = redis_client.xreadgroup(
            groupname=redis_settings.HEDWIG_QUEUE,
            consumername="test-client",
            streams={dlq_stream: ">"},
            count=1,
        )
        assert len(entries) == 1
        assert dlq_stream in entries
        _, msg_payload = entries[dlq_stream][0][0]
        assert_redis_message_payload(message, msg_payload)

        # validate original message is no longer available in origin stream,
        # because it was confirmed with XACK.
        entries = redis_client.xautoclaim(
            name="hedwig:dev-trip-created-v1",
            groupname=redis_settings.HEDWIG_QUEUE,
            consumername="test-client",
            min_idle_time=0,
            start_id="0-0",
            count=1,
            justid=True,
        )
        assert len(entries) == 0

    def test_success_requeue_dead_letter(self, message, redis_client, redis_settings):
        redis_settings.HEDWIG_VISIBILITY_TIMEOUT_S = 0.1
        message.publish()

        # move valid message to dlq
        redis_consumer = redis.RedisStreamsConsumerBackend()
        items = list(redis_consumer.pull_messages(num_messages=1))
        assert len(items) == 1
        sleep(0.5)
        redis_consumer = redis.RedisStreamsConsumerBackend()
        items = list(redis_consumer.pull_messages(num_messages=1))
        assert len(items) == 0
        # claimed messaged - requeue dlq scenario 1
        dlq_stream = redis_consumer._deadletter_stream.encode()
        dlq_entries = redis_client.xreadgroup(
            groupname=redis_settings.HEDWIG_QUEUE,
            consumername="test-client",
            streams={dlq_stream: ">"},
            count=1,
        )
        assert len(dlq_entries) == 1

        # available dlq message - requeue dlq scenario 2
        payload, attributes = message.serialize()
        if isinstance(payload, bytes):
            payload = base64.encodebytes(payload).decode()
            attributes['hedwig_encoding'] = 'base64'
        redis_message = {"hedwig_payload": payload, **attributes}
        redis_client.xadd(dlq_stream, redis_message)

        requeue_dead_letter()

        _, dlq_entries, _ = redis_client.xautoclaim(
            name=dlq_stream,
            groupname=redis_settings.HEDWIG_QUEUE,
            consumername="test-client",
            min_idle_time=0,
            start_id="0-0",
            count=1,
        )
        assert len(dlq_entries) == 0

        main_stream = redis_consumer._main_stream.encode()
        entries = redis_client.xreadgroup(
            groupname=redis_settings.HEDWIG_QUEUE,
            consumername="test-client",
            streams={main_stream: ">"},
            count=10,
        )
        assert len(entries[main_stream][0]) == 2
        for _, msg_payload in entries[main_stream][0]:
            assert_redis_message_payload(message, msg_payload)

    def test_fetch_and_process_messages_success(
        self, message_factory, redis_client, redis_settings, prepost_process_hooks
    ):
        def message_handler(message: Message):
            assert message.id == trip_created_message.id
            assert message.data == trip_created_message.data

        redis_settings.HEDWIG_CALLBACKS = {('trip_created', '1.*'): message_handler}
        trip_created_message = message_factory(msg_type=MessageType.trip_created)
        _publish_and_consume_message(trip_created_message)

        pre_process_hook.assert_called_once_with()
        post_process_hook.assert_called_once_with()
        heartbeat_hook.assert_called_once_with(error_count=0)
        # assert that XACK was successfully sent and there is no message available
        _, entries, _ = redis_client.xautoclaim(
            name=b'hedwig:dev-trip-created-v1',
            groupname=redis_settings.HEDWIG_QUEUE,
            consumername="test-client",
            min_idle_time=0,
            start_id="0-0",
            count=1,
        )
        assert len(entries) == 0

    def test_fetch_and_process_messages_failure(
        self, message_factory, redis_client, redis_settings, prepost_process_hooks
    ):
        def message_handler(message: Message):
            raise Exception("error during message processing")

        redis_settings.HEDWIG_CALLBACKS = {('trip_created', '1.*'): message_handler}
        trip_created_message = message_factory(msg_type=MessageType.trip_created)
        msg_id = _publish_and_consume_message(trip_created_message)

        pre_process_hook.assert_called_once_with()
        post_process_hook.assert_not_called()
        heartbeat_hook.assert_called_once_with(error_count=1)
        # assert that XACK was not sent and message is still available
        _, entries, _ = redis_client.xautoclaim(
            name=b'hedwig:dev-trip-created-v1',
            groupname=redis_settings.HEDWIG_QUEUE,
            consumername="test-client",
            min_idle_time=0,
            start_id="0-0",
            count=1,
        )
        assert len(entries) == 1
        assert entries[0][0] == msg_id

    def test_success_extend_visibility_timeout(
        self, message_factory, redis_client, redis_settings, prepost_process_hooks
    ):
        def message_handler(message: Message):
            sleep(1)
            message.extend_visibility_timeout(redis_settings.HEDWIG_VISIBILITY_TIMEOUT_S)
            # raise error to avoid sending XACK to keep message in PEL (Pending Entries List)
            raise Exception("error during message processing")

        redis_settings.HEDWIG_CALLBACKS = {('trip_created', '1.*'): message_handler}
        trip_created_message = message_factory(msg_type=MessageType.trip_created, id=str(message_factory))
        msg_id = _publish_and_consume_message(trip_created_message)

        heartbeat_hook.assert_called_once_with(error_count=1)
        metadata = redis_client.xpending_range(
            "hedwig:dev-trip-created-v1", redis_settings.HEDWIG_QUEUE, msg_id, msg_id, 1
        )
        assert metadata[0]["time_since_delivered"] < 500

    def test_extend_visibility_timeout_invalid_timeout_value(self, message, redis_settings):
        with pytest.raises(AssertionError) as err:
            message.extend_visibility_timeout(1000)

        assert "Visibility timeout is not configurable" in str(err.value)
