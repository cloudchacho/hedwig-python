import json
from unittest import mock

import pytest
from google.cloud.pubsub_v1.types import FlowControl

from hedwig.backends import gcp
from hedwig.backends.gcp import GoogleMetadata
from hedwig.conf import settings
from hedwig.exceptions import ValidationError, CallbackNotFound
from hedwig.testing.factories import MessageFactory

from tests.models import MessageType


@pytest.fixture(autouse=True)
def gcp_settings(settings):
    settings.GOOGLE_APPLICATION_CREDENTIALS = "DUMMY_GOOGLE_APPLICATION_CREDENTIALS"
    settings.HEDWIG_PUBLISHER_BACKEND = "hedwig.backends.gcp.GooglePubSubPublisherBackend"
    settings.HEDWIG_CONSUMER_BACKEND = "hedwig.backends.gcp.GooglePubSubConsumerBackend"
    settings.GOOGLE_CLOUD_PROJECT = "DUMMY_PROJECT_ID"
    settings.GOOGLE_PUBSUB_READ_TIMEOUT_S = 5
    settings.HEDWIG_GOOGLE_MESSAGE_RETRY_STATE_BACKEND = 'hedwig.backends.gcp.MessageRetryStateLocMem'
    settings.HEDWIG_GOOGLE_MESSAGE_MAX_RETRIES = 5
    settings.HEDWIG_QUEUE = settings.HEDWIG_QUEUE.lower()
    settings.HEDWIG_SUBSCRIPTIONS = ['topic1', 'topic2']
    yield settings


@pytest.fixture
def retry_once_settings(gcp_settings):
    gcp_settings.HEDWIG_GOOGLE_MESSAGE_MAX_RETRIES = 1
    yield gcp_settings


class TestPubSubPublisher:
    def test_publish_success(self, mock_pubsub_v1, message, gcp_settings):
        gcp_publisher = gcp.GooglePubSubPublisherBackend()
        gcp_publisher.publisher.topic_path = mock.MagicMock(return_value="dummy_topic_path")
        message_data = json.dumps(message.as_dict())

        message_id = gcp_publisher.publish(message)

        assert message_id == gcp_publisher.publisher.publish.return_value.result()

        mock_pubsub_v1.PublisherClient.assert_called_once_with(batch_settings=())
        gcp_publisher.publisher.topic_path.assert_called_once_with(
            gcp_settings.GOOGLE_CLOUD_PROJECT, f'hedwig-{message.topic}'
        )
        gcp_publisher.publisher.publish.assert_called_once_with(
            "dummy_topic_path", data=message_data.encode(), **message.headers
        )

    def test_sync_publish_success(self, mock_pubsub_v1, message, gcp_settings):
        gcp_publisher = gcp.GooglePubSubAsyncPublisherBackend()
        gcp_publisher.publisher.topic_path = mock.MagicMock(return_value="dummy_topic_path")
        message_data = json.dumps(message.as_dict())

        future = gcp_publisher.publish(message)

        assert future == gcp_publisher.publisher.publish.return_value

        mock_pubsub_v1.PublisherClient.assert_called_once_with(batch_settings=())
        gcp_publisher.publisher.topic_path.assert_called_once_with(
            gcp_settings.GOOGLE_CLOUD_PROJECT, f'hedwig-{message.topic}'
        )
        gcp_publisher.publisher.publish.assert_called_once_with(
            "dummy_topic_path", data=message_data.encode(), **message.headers
        )

    @mock.patch('tests.handlers._trip_created_handler', autospec=True)
    def test_sync_mode(self, callback_mock, mock_pubsub_v1, message, mock_publisher_backend, gcp_settings):
        gcp_settings.HEDWIG_SYNC = True

        message.publish()
        callback_mock.assert_called_once_with(message)

    def test_sync_mode_detects_invalid_callback(self, gcp_settings, mock_pubsub_v1):
        gcp_settings.HEDWIG_SYNC = True

        message = MessageFactory(msg_type=MessageType.vehicle_created)
        with pytest.raises(ValidationError) as exc_info:
            message.publish()
        assert isinstance(exc_info.value.__context__, CallbackNotFound)


pre_process_hook = mock.MagicMock()
post_process_hook = mock.MagicMock()


@pytest.fixture(name='subscription_paths')
def _subscription_paths(gcp_settings):
    return [mock.MagicMock() for _ in range(len(gcp_settings.HEDWIG_SUBSCRIPTIONS) + 1)]


@pytest.fixture(name='gcp_consumer')
def _gcp_consumer(mock_pubsub_v1, gcp_settings, subscription_paths):
    mock_pubsub_v1.SubscriberClient.subscription_path.side_effect = subscription_paths
    return gcp.GooglePubSubConsumerBackend()


@pytest.fixture(name='prepost_process_hooks')
def _prepost_process_hooks(gcp_settings):
    gcp_settings.HEDWIG_PRE_PROCESS_HOOK = 'tests.test_backends.test_gcp.pre_process_hook'
    gcp_settings.HEDWIG_POST_PROCESS_HOOK = 'tests.test_backends.test_gcp.post_process_hook'
    yield
    pre_process_hook.reset_mock()
    post_process_hook.reset_mock()


class TestGCPConsumer:
    @staticmethod
    def _build_gcp_queue_message(message):
        queue_message = mock.MagicMock()
        queue_message.ack_id = "dummy_ack_id"
        queue_message.data = json.dumps(message.as_dict()).encode()
        queue_message.message.attributes = message.as_dict()['metadata']['headers']
        return queue_message

    def test_pull_messages(self, mock_pubsub_v1, gcp_consumer, subscription_paths, timed_shutdown_event):
        num_messages = 1
        visibility_timeout = 10
        messages = [mock.MagicMock(), mock.MagicMock(), mock.MagicMock()]
        futures = [mock.MagicMock(), mock.MagicMock(), mock.MagicMock()]

        def subscribe_side_effect(subscription_path, callback, flow_control, scheduler):
            # send message
            scheduler.schedule(None, message=messages[gcp_consumer.subscriber.subscribe.call_count - 1])

            # return a "future"
            return futures[gcp_consumer.subscriber.subscribe.call_count - 1]

        gcp_consumer.subscriber.subscribe.side_effect = subscribe_side_effect

        messages_received = list(
            gcp_consumer.pull_messages(num_messages, visibility_timeout, shutdown_event=timed_shutdown_event)
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
                mock.call(settings.GOOGLE_CLOUD_PROJECT, f'hedwig-{settings.HEDWIG_QUEUE}'),
            ]
        )

        # futures must be canceled on shutdown
        for future in futures:
            future.cancel.assert_called_once_with()

        # fetch the right number of messages
        flow_control = FlowControl(max_messages=num_messages, max_lease_duration=visibility_timeout)

        # verify subscriber call for each path
        gcp_consumer.subscriber.subscribe.assert_has_calls(
            [
                mock.call(subscription_paths[x], callback=None, flow_control=flow_control, scheduler=mock.ANY)
                for x in range(3)
            ]
        )

    def test_success_extend_visibility_timeout(self, gcp_consumer):
        visibility_timeout_s = 10
        ack_id = "dummy_ack_id"
        subscription_path = "subscriptions/foobar"

        gcp_consumer.extend_visibility_timeout(visibility_timeout_s, GoogleMetadata(ack_id, subscription_path))

        gcp_consumer.subscriber.modify_ack_deadline.assert_called_once_with(
            subscription_path, [ack_id], visibility_timeout_s
        )

    @pytest.mark.parametrize("visibility_timeout", [-1, 601])
    def test_failure_extend_visibility_timeout(self, visibility_timeout, gcp_consumer):
        subscription_path = "subscriptions/foobar"

        with pytest.raises(ValueError):
            gcp_consumer.extend_visibility_timeout(
                visibility_timeout, GoogleMetadata('dummy_ack_id', subscription_path)
            )

        gcp_consumer.subscriber.subscription_path.assert_not_called()
        gcp_consumer.subscriber.modify_ack_deadline.assert_not_called()

    def test_success_requeue_dead_letter(self, mock_pubsub_v1, message):
        gcp_consumer = gcp.GooglePubSubConsumerBackend(dlq=True)

        num_messages = 1
        visibility_timeout = 4
        subscription_path = gcp_consumer._subscription_paths[0]

        queue_message = self._build_gcp_queue_message(message)
        response = mock.MagicMock()
        response.received_messages = [queue_message]
        response2 = mock.MagicMock()
        response2.received_messages = []
        gcp_consumer.subscriber.pull.side_effect = iter([response, response2])

        gcp_consumer.requeue_dead_letter(num_messages=num_messages, visibility_timeout=visibility_timeout)

        gcp_consumer.subscriber.modify_ack_deadline.assert_called_once_with(
            subscription_path, [queue_message.ack_id], visibility_timeout
        )
        gcp_consumer.subscriber.pull.assert_has_calls(
            [
                mock.call(subscription_path, num_messages, retry=None, timeout=settings.GOOGLE_PUBSUB_READ_TIMEOUT_S),
                mock.call(subscription_path, num_messages, retry=None, timeout=settings.GOOGLE_PUBSUB_READ_TIMEOUT_S),
            ]
        )
        gcp_consumer._publisher.publish.assert_called_once_with(
            mock_pubsub_v1.PublisherClient.topic_path.return_value, data=queue_message.message.data, **message.headers
        )
        gcp_consumer.subscriber.acknowledge.assert_called_once_with(subscription_path, [queue_message.ack_id])

    def test_fetch_and_process_messages_success(
        self, gcp_consumer, message, timed_shutdown_event, subscription_paths, prepost_process_hooks
    ):
        num_messages = 3
        visibility_timeout = 4

        queue_message = self._build_gcp_queue_message(message)

        def subscribe_side_effect(subscription_path, callback, flow_control, scheduler):
            if gcp_consumer.subscriber.subscribe.call_count == 1:
                # send message
                scheduler.schedule(None, message=queue_message)

            # return a "future"
            return mock.MagicMock()

        gcp_consumer.subscriber.subscribe.side_effect = subscribe_side_effect
        gcp_consumer.process_message = mock.MagicMock(wraps=gcp_consumer.process_message)
        gcp_consumer.message_handler = mock.MagicMock(wraps=gcp_consumer.message_handler)

        gcp_consumer.fetch_and_process_messages(
            num_messages=num_messages, visibility_timeout=visibility_timeout, shutdown_event=timed_shutdown_event
        )

        # fetch the right number of messages
        flow_control = FlowControl(max_messages=num_messages, max_lease_duration=visibility_timeout)

        gcp_consumer.subscriber.subscribe.assert_called_with(
            subscription_paths[-1], callback=None, flow_control=flow_control, scheduler=mock.ANY
        )
        gcp_consumer.process_message.assert_called_once_with(mock.ANY)
        assert gcp_consumer.process_message.call_args[0][0].message == queue_message
        gcp_consumer.message_handler.assert_called_once_with(
            queue_message.data.decode(), GoogleMetadata(queue_message.ack_id, subscription_paths[0])
        )
        queue_message.ack.assert_called_once_with()
        pre_process_hook.assert_called_once_with(google_pubsub_message=queue_message)
        post_process_hook.assert_called_once_with(google_pubsub_message=queue_message)

    def test_message_moved_to_dlq(self, retry_once_settings, gcp_consumer, message, timed_shutdown_event):
        queue_message = self._build_gcp_queue_message(message)

        def pull_messages_side_effect(*args, **kwargs):
            if gcp_consumer.pull_messages.call_count == 1:
                # send message
                return [queue_message]

            return []

        gcp_consumer.pull_messages = mock.MagicMock(side_effect=pull_messages_side_effect)
        gcp_consumer.message_handler = mock.MagicMock(side_effect=Exception)

        gcp_consumer.fetch_and_process_messages(shutdown_event=timed_shutdown_event)

        gcp_consumer._publisher.publish.assert_called_once_with(
            gcp_consumer._dlq_topic_path, queue_message.message.data, **message.headers
        )
        gcp_consumer._publisher.publish.return_value.result.assert_called_once_with()

    def test_message_not_moved_to_dlq(self, gcp_consumer, message, timed_shutdown_event):
        queue_message = self._build_gcp_queue_message(message)

        def pull_messages_side_effect(*args, **kwargs):
            if gcp_consumer.pull_messages.call_count == 1:
                # send message
                return [queue_message]

            return []

        gcp_consumer.pull_messages = mock.MagicMock(side_effect=pull_messages_side_effect)
        gcp_consumer.message_handler = mock.MagicMock(side_effect=Exception)

        gcp_consumer.fetch_and_process_messages(shutdown_event=timed_shutdown_event)

        gcp_consumer._publisher.publish.assert_not_called()
