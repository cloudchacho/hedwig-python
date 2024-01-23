import threading
from datetime import datetime, timedelta, timezone
from unittest import mock

import freezegun
import pytest

try:
    from google.cloud.pubsub_v1.types import FlowControl
except ImportError:
    pass

try:
    from hedwig.backends.gcp import GoogleMetadata
    from tests.utils.gcp import build_gcp_queue_message, build_gcp_received_message
except ImportError:
    pass
from hedwig.conf import settings
from hedwig.exceptions import ValidationError, CallbackNotFound

from tests.models import MessageType


gcp = pytest.importorskip('hedwig.backends.gcp')


@pytest.fixture(autouse=True)
def gcp_settings(settings):
    settings.GOOGLE_APPLICATION_CREDENTIALS = "DUMMY_GOOGLE_APPLICATION_CREDENTIALS"
    settings.HEDWIG_PUBLISHER_BACKEND = "hedwig.backends.gcp.GooglePubSubPublisherBackend"
    settings.HEDWIG_CONSUMER_BACKEND = "hedwig.backends.gcp.GooglePubSubConsumerBackend"
    settings.GOOGLE_CLOUD_PROJECT = "DUMMY_PROJECT_ID"
    settings.GOOGLE_PUBSUB_READ_TIMEOUT_S = 5
    settings.HEDWIG_QUEUE = settings.HEDWIG_QUEUE.lower()
    settings.HEDWIG_SUBSCRIPTIONS = ['topic1', 'topic2', ('topic3', 'other-project')]
    yield settings


class TestPubSubPublisher:
    def test__get_topic_path(self, mock_pubsub_v1, message_factory):
        gcp_publisher = gcp.GooglePubSubPublisherBackend()
        message = message_factory(msg_type=MessageType.vehicle_created)
        assert gcp_publisher._get_topic_path(message) == gcp_publisher.publisher.topic_path.return_value
        gcp_publisher.publisher.topic_path.assert_called_once_with(
            'project-id-or-account-id', 'hedwig-dev-vehicle-created-v1'
        )

    def test_publish_success(self, mock_pubsub_v1, message, gcp_settings, use_transport_message_attrs):
        gcp_publisher = gcp.GooglePubSubPublisherBackend()
        gcp_publisher.publisher.topic_path = mock.MagicMock(return_value="dummy_topic_path")

        message_id = gcp_publisher.publish(message)

        assert message_id == gcp_publisher.publisher.publish.return_value.result()

        payload, attributes = message.serialize()
        if not use_transport_message_attrs:
            attributes = message.headers
        if isinstance(payload, str):
            payload = payload.encode('utf8')
            attributes["hedwig_encoding"] = 'utf8'

        mock_pubsub_v1.PublisherClient.assert_called_once_with(batch_settings=())
        gcp_publisher.publisher.topic_path.assert_called_once_with(
            gcp_settings.GOOGLE_CLOUD_PROJECT, f'hedwig-{gcp_publisher.topic(message)}'
        )
        gcp_publisher.publisher.publish.assert_called_once_with("dummy_topic_path", data=payload, **attributes)

    def test_sync_publish_success(self, mock_pubsub_v1, message, gcp_settings, use_transport_message_attrs):
        gcp_publisher = gcp.GooglePubSubAsyncPublisherBackend()
        gcp_publisher.publisher.topic_path = mock.MagicMock(return_value="dummy_topic_path")
        payload, attributes = message.serialize()

        future = gcp_publisher.publish(message)
        assert future == gcp_publisher.publisher.publish.return_value

        if not use_transport_message_attrs:
            attributes = message.headers
        if isinstance(payload, str):
            payload = payload.encode('utf8')
            attributes["hedwig_encoding"] = 'utf8'

        mock_pubsub_v1.PublisherClient.assert_called_once_with(batch_settings=())
        gcp_publisher.publisher.topic_path.assert_called_once_with(
            gcp_settings.GOOGLE_CLOUD_PROJECT, f'hedwig-{gcp_publisher.topic(message)}'
        )
        gcp_publisher.publisher.publish.assert_called_once_with("dummy_topic_path", data=payload, **attributes)

    @freezegun.freeze_time()
    @mock.patch('tests.handlers._trip_created_handler', autospec=True)
    def test_sync_mode(self, callback_mock, mock_pubsub_v1, message, mock_publisher_backend, gcp_settings):
        gcp_settings.HEDWIG_SYNC = True

        receipt = 'test-receipt'
        publish_time = datetime.now(timezone.utc)
        delivery_attempt = 1

        message.publish()
        callback_mock.assert_called_once_with(
            message.with_provider_metadata(GoogleMetadata(receipt, 'test-subscription', publish_time, delivery_attempt))
        )

    def test_sync_mode_detects_invalid_callback(self, gcp_settings, mock_pubsub_v1, message_factory):
        gcp_settings.HEDWIG_SYNC = True

        message = message_factory(msg_type=MessageType.vehicle_created)
        with pytest.raises(ValidationError) as exc_info:
            message.publish()
        assert isinstance(exc_info.value.__context__, CallbackNotFound)


pre_process_hook = mock.MagicMock()
post_process_hook = mock.MagicMock()
heartbeat_hook = mock.MagicMock()


@pytest.fixture(name='subscription_paths')
def _subscription_paths(gcp_settings):
    return [mock.MagicMock() for _ in range(len(gcp_settings.HEDWIG_SUBSCRIPTIONS) + 1)]


@pytest.fixture(name='gcp_consumer')
def _gcp_consumer(mock_pubsub_v1, gcp_settings, subscription_paths):
    mock_pubsub_v1.SubscriberClient.subscription_path.side_effect = subscription_paths
    return gcp.GooglePubSubConsumerBackend()


@pytest.fixture(name='prepost_process_hooks')
def _prepost_process_hooks(gcp_settings):
    gcp_settings.HEDWIG_HEARTBEAT_HOOK = 'tests.test_backends.test_gcp.heartbeat_hook'
    gcp_settings.HEDWIG_PRE_PROCESS_HOOK = 'tests.test_backends.test_gcp.pre_process_hook'
    gcp_settings.HEDWIG_POST_PROCESS_HOOK = 'tests.test_backends.test_gcp.post_process_hook'
    yield
    pre_process_hook.reset_mock(side_effect=True)
    post_process_hook.reset_mock(side_effect=True)
    heartbeat_hook.reset_mock(side_effect=True)


class TestGCPConsumer:
    def test_pull_messages(self, mock_pubsub_v1, gcp_consumer, subscription_paths, prepost_process_hooks):
        shutdown_event = threading.Event()
        num_messages = 1
        visibility_timeout = 10
        messages = [mock.MagicMock(), mock.MagicMock(), mock.MagicMock(), mock.MagicMock()]
        futures = [mock.MagicMock(), mock.MagicMock(), mock.MagicMock(), mock.MagicMock()]

        def subscribe_side_effect(subscription_path, callback, flow_control, scheduler):
            # send message
            scheduler.schedule(None, message=messages[gcp_consumer.subscriber.subscribe.call_count - 1])

            if gcp_consumer.subscriber.subscribe.call_count == len(messages):
                shutdown_event.set()

            # return a "future"
            return futures[gcp_consumer.subscriber.subscribe.call_count - 1]

        gcp_consumer.subscriber.subscribe.side_effect = subscribe_side_effect

        messages_received = list(
            gcp_consumer.pull_messages(num_messages, visibility_timeout, shutdown_event=shutdown_event)
        )

        # unwrap messages
        assert [m.message for m in messages_received] == messages

        # should look up all subscription paths correctly
        mock_pubsub_v1.SubscriberClient.subscription_path.assert_has_calls(
            [
                mock.call(
                    settings.GOOGLE_CLOUD_PROJECT, f'hedwig-{settings.HEDWIG_QUEUE}-{settings.HEDWIG_SUBSCRIPTIONS[0]}'
                ),
                mock.call(
                    settings.GOOGLE_CLOUD_PROJECT, f'hedwig-{settings.HEDWIG_QUEUE}-{settings.HEDWIG_SUBSCRIPTIONS[1]}'
                ),
                mock.call(
                    settings.GOOGLE_CLOUD_PROJECT,
                    f'hedwig-{settings.HEDWIG_QUEUE}-{settings.HEDWIG_SUBSCRIPTIONS[2][1]}-'
                    f'{settings.HEDWIG_SUBSCRIPTIONS[2][0]}',
                ),
                mock.call(settings.GOOGLE_CLOUD_PROJECT, f'hedwig-{settings.HEDWIG_QUEUE}'),
            ]
        )

        # futures must be canceled on shutdown
        for future in futures:
            future.cancel.assert_called_once_with()

        # fetch the right number of messages
        flow_control = FlowControl(max_messages=num_messages, max_duration_per_lease_extension=visibility_timeout)

        # verify subscriber call for each path
        gcp_consumer.subscriber.subscribe.assert_has_calls(
            [
                mock.call(subscription_paths[x], callback=None, flow_control=flow_control, scheduler=mock.ANY)
                for x in range(4)
            ]
        )
        heartbeat_hook.assert_called_once_with(error_count=0)

    @pytest.mark.parametrize(
        "inactivity_s,last_message_received_delta_s,expected_error_count",
        [(None, 0, 1), (10, 1, 1), (1, 2, 0)],
        ids=["reset-disabled", "reset-enabled-inactivity-period-not-reached", "reset-enabled"],
    )
    def test_pull_messages_error_count_inactivity_reset(
        self,
        mock_pubsub_v1,
        gcp_settings,
        subscription_paths,
        prepost_process_hooks,
        inactivity_s,
        last_message_received_delta_s,
        expected_error_count,
    ):
        class _Event(threading.Event):
            def __init__(self, max_calls):
                super().__init__()
                self.max_calls = max_calls
                self.counter = 0

            def is_set(self):
                if self.counter == self.max_calls:
                    self.set()
                self.counter += 1
                return super().is_set()

        shutdown_event = _Event(max_calls=1)
        num_messages = 1
        visibility_timeout = 10
        mock_pubsub_v1.SubscriberClient.subscription_path.side_effect = subscription_paths
        gcp_settings.HEDWIG_HEARTBEAT_INACTIVITY_RESET_S = inactivity_s
        gcp_consumer = gcp.GooglePubSubConsumerBackend()
        gcp_consumer._last_message_received_at = datetime.utcnow() - timedelta(seconds=last_message_received_delta_s)
        gcp_consumer._error_count = 1

        list(gcp_consumer.pull_messages(num_messages, visibility_timeout, shutdown_event=shutdown_event))

        assert gcp_consumer._error_count == expected_error_count
        heartbeat_hook.assert_called_once_with(error_count=expected_error_count)

    def test_success_extend_visibility_timeout(self, gcp_consumer, prepost_process_hooks):
        visibility_timeout_s = 10
        ack_id = "dummy_ack_id"
        subscription_path = "subscriptions/foobar"
        publish_time = datetime.now(timezone.utc)
        delivery_attempt = 1

        gcp_consumer.extend_visibility_timeout(
            visibility_timeout_s, GoogleMetadata(ack_id, subscription_path, publish_time, delivery_attempt)
        )

        gcp_consumer.subscriber.modify_ack_deadline.assert_called_once_with(
            subscription=subscription_path, ack_ids=[ack_id], ack_deadline_seconds=visibility_timeout_s
        )
        heartbeat_hook.assert_called_once_with(error_count=0)

    @pytest.mark.parametrize("visibility_timeout", [-1, 601])
    def test_failure_extend_visibility_timeout(self, visibility_timeout, gcp_consumer, prepost_process_hooks):
        subscription_path = "subscriptions/foobar"
        publish_time = datetime.now(timezone.utc)
        delivery_attempt = 1

        with pytest.raises(ValueError):
            gcp_consumer.extend_visibility_timeout(
                visibility_timeout, GoogleMetadata('dummy_ack_id', subscription_path, publish_time, delivery_attempt)
            )

        gcp_consumer.subscriber.subscription_path.assert_not_called()
        gcp_consumer.subscriber.modify_ack_deadline.assert_not_called()
        heartbeat_hook.assert_not_called()

    def test_success_requeue_dead_letter(self, mock_pubsub_v1, message, use_transport_message_attrs):
        gcp_consumer = gcp.GooglePubSubConsumerBackend(dlq=True)

        num_messages = 1
        visibility_timeout = 4
        subscription_path = gcp_consumer._subscription_paths[0]

        queue_message = build_gcp_received_message(message)
        response = mock.MagicMock()
        response.received_messages = [queue_message]
        response2 = mock.MagicMock()
        response2.received_messages = []
        gcp_consumer.subscriber.pull.side_effect = iter([response, response2])

        gcp_consumer.requeue_dead_letter(num_messages=num_messages, visibility_timeout=visibility_timeout)

        gcp_consumer.subscriber.modify_ack_deadline.assert_called_once_with(
            subscription=subscription_path, ack_ids=[queue_message.ack_id], ack_deadline_seconds=visibility_timeout
        )
        gcp_consumer.subscriber.pull.assert_has_calls(
            [
                mock.call(
                    subscription=subscription_path,
                    max_messages=num_messages,
                    retry=None,
                    timeout=settings.GOOGLE_PUBSUB_READ_TIMEOUT_S,
                ),
                mock.call(
                    subscription=subscription_path,
                    max_messages=num_messages,
                    retry=None,
                    timeout=settings.GOOGLE_PUBSUB_READ_TIMEOUT_S,
                ),
            ]
        )
        gcp_consumer._publisher.publish.assert_called_once_with(
            mock_pubsub_v1.PublisherClient.topic_path.return_value,
            data=queue_message.message.data,
            **queue_message.message.attributes,
        )
        gcp_consumer.subscriber.acknowledge.assert_called_once_with(
            subscription=subscription_path, ack_ids=[queue_message.ack_id]
        )

    def test_fetch_and_process_messages_success(
        self,
        gcp_consumer,
        message,
        subscription_paths,
        prepost_process_hooks,
        use_transport_message_attrs,
    ):
        shutdown_event = threading.Event()
        num_messages = 3
        visibility_timeout = 4

        queue_message = build_gcp_queue_message(message)

        def subscribe_side_effect(subscription_path, callback, flow_control, scheduler):
            if gcp_consumer.subscriber.subscribe.call_count == 1:
                # send message
                scheduler.schedule(None, message=queue_message)

            shutdown_event.set()

            # return a "future"
            return mock.MagicMock()

        gcp_consumer.subscriber.subscribe.side_effect = subscribe_side_effect
        gcp_consumer.process_message = mock.MagicMock(wraps=gcp_consumer.process_message)
        gcp_consumer.message_handler = mock.MagicMock(wraps=gcp_consumer.message_handler)

        gcp_consumer.fetch_and_process_messages(
            num_messages=num_messages, visibility_timeout=visibility_timeout, shutdown_event=shutdown_event
        )

        # fetch the right number of messages
        flow_control = FlowControl(max_messages=num_messages, max_duration_per_lease_extension=visibility_timeout)

        gcp_consumer.subscriber.subscribe.assert_called_with(
            subscription_paths[-1], callback=None, flow_control=flow_control, scheduler=mock.ANY
        )
        gcp_consumer.process_message.assert_called_once_with(mock.ANY)
        assert gcp_consumer.process_message.call_args[0][0].message == queue_message
        if queue_message.attributes.get('hedwig_encoding') == 'utf8':
            payload = queue_message.data.decode('utf8')
        else:
            payload = queue_message.data
        gcp_consumer.message_handler.assert_called_once_with(
            payload,
            queue_message.attributes,
            GoogleMetadata(
                queue_message.ack_id,
                subscription_paths[0],
                queue_message.publish_time,
                queue_message.delivery_attempt,
            ),
        )
        queue_message.ack.assert_called_once_with()
        pre_process_hook.assert_called_once_with(google_pubsub_message=queue_message)
        post_process_hook.assert_called_once_with(google_pubsub_message=queue_message)
        heartbeat_hook.assert_called_once_with(error_count=0)
