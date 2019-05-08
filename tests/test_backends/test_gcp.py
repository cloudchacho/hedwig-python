import json
from unittest import mock

import pytest

from hedwig.backends import gcp
from hedwig.backends.gcp import GoogleMetadata
from hedwig.conf import settings
from hedwig.exceptions import ValidationError, CallbackNotFound
from hedwig.models import MessageType
from hedwig.testing.factories import MessageFactory


@pytest.fixture
def gcp_settings(settings):
    settings.GOOGLE_APPLICATION_CREDENTIALS = "DUMMY_GOOGLE_APPLICATION_CREDENTIALS"
    settings.HEDWIG_PUBLISHER_BACKEND = "hedwig.backends.gcp.GooglePubSubPublisherBackend"
    settings.HEDWIG_CONSUMER_BACKEND = "hedwig.backends.gcp.GooglePubSubConsumerBackend"
    settings.GOOGLE_PUBSUB_PROJECT_ID = "DUMMY_PROJECT_ID"
    settings.GOOGLE_PUBSUB_READ_TIMEOUT_S = 5
    settings.HEDWIG_GOOGLE_MESSAGE_RETRY_STATE_BACKEND = 'hedwig.backends.gcp.MessageRetryStateLocMem'
    settings.HEDWIG_GOOGLE_MESSAGE_MAX_RETRIES = 5
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

        gcp_publisher.publish(message)

        mock_pubsub_v1.PublisherClient.from_service_account_file.assert_called_once_with(
            gcp_settings.GOOGLE_APPLICATION_CREDENTIALS
        )
        gcp_publisher.publisher.topic_path.assert_called_once_with(
            gcp_settings.GOOGLE_PUBSUB_PROJECT_ID, f'hedwig-{message.topic}'
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


class TestGCPConsumer:
    def setup(self):
        self.gcp_consumer = gcp.GooglePubSubConsumerBackend()

        pre_process_hook.reset_mock()
        post_process_hook.reset_mock()

    @staticmethod
    def _build_gcp_queue_message(message):
        queue_message = mock.MagicMock()
        queue_message.ack_id = "dummy_ack_id"
        queue_message.message.data = json.dumps(message.as_dict()).encode()
        queue_message.attributes = message.as_dict()['metadata']['headers']
        return queue_message

    def test_initialization(self, mock_pubsub_v1, gcp_settings):
        mock_pubsub_v1.SubscriberClient.from_service_account_file.assert_called_once_with(
            settings.GOOGLE_APPLICATION_CREDENTIALS
        )

    def test_pull_messages(self, mock_pubsub_v1, gcp_settings):
        num_messages = 1
        visibility_timeout = 10

        self.gcp_consumer.pull_messages(num_messages, visibility_timeout)

        mock_pubsub_v1.SubscriberClient.subscription_path.assert_called_once_with(
            settings.GOOGLE_PUBSUB_PROJECT_ID, f'hedwig-{settings.HEDWIG_QUEUE}'
        )

        self.gcp_consumer.subscriber.pull.assert_called_once_with(
            mock_pubsub_v1.SubscriberClient.subscription_path.return_value,
            num_messages,
            retry=None,
            timeout=gcp_settings.GOOGLE_PUBSUB_READ_TIMEOUT_S,
        )

    def test_success_extend_visibility_timeout(self, mock_pubsub_v1, gcp_settings):
        visibility_timeout_s = 10
        ack_id = "dummy_ack_id"

        self.gcp_consumer.extend_visibility_timeout(visibility_timeout_s, GoogleMetadata(ack_id))

        self.gcp_consumer.subscriber.modify_ack_deadline.assert_called_once_with(
            mock_pubsub_v1.SubscriberClient.subscription_path.return_value, [ack_id], visibility_timeout_s
        )

    @pytest.mark.parametrize("visibility_timeout", [-1, 601])
    def test_failure_extend_visibility_timeout(self, visibility_timeout, mock_pubsub_v1):
        with pytest.raises(ValueError):
            self.gcp_consumer.extend_visibility_timeout(visibility_timeout, GoogleMetadata('dummy_ack_id'))

        self.gcp_consumer.subscriber.subscription_path.assert_not_called()
        self.gcp_consumer.subscriber.modify_ack_deadline.assert_not_called()

    def test_success_requeue_dead_letter(self, mock_pubsub_v1, gcp_settings, message):
        self.gcp_consumer = gcp.GooglePubSubConsumerBackend(dlq=True)

        num_messages = 1
        visibility_timeout = 4

        queue_message = self._build_gcp_queue_message(message)
        self.gcp_consumer.pull_messages = mock.MagicMock(side_effect=iter([[queue_message], None]))

        self.gcp_consumer.requeue_dead_letter(num_messages=num_messages, visibility_timeout=visibility_timeout)

        self.gcp_consumer.subscriber.modify_ack_deadline.assert_called_once_with(
            [queue_message.ack_id], visibility_timeout
        )
        self.gcp_consumer.pull_messages.assert_has_calls(
            [
                mock.call(num_messages=num_messages, visibility_timeout=visibility_timeout),
                mock.call(num_messages=num_messages, visibility_timeout=visibility_timeout),
            ]
        )
        self.gcp_consumer._publisher.publish.assert_called_once_with(
            mock_pubsub_v1.PublisherClient.topic_path.return_value, data=queue_message.message.data, **message.headers
        )
        self.gcp_consumer.subscriber.acknowledge.assert_called_once_with(
            self.gcp_consumer._subscription_path, [queue_message.ack_id]
        )

    def test_fetch_and_process_messages_success(self, mock_pubsub_v1, gcp_settings, message):
        gcp_settings.HEDWIG_PRE_PROCESS_HOOK = 'tests.test_backends.test_gcp.pre_process_hook'
        gcp_settings.HEDWIG_POST_PROCESS_HOOK = 'tests.test_backends.test_gcp.post_process_hook'
        num_messages = 3
        visibility_timeout = 4

        queue_message = self._build_gcp_queue_message(message)
        received_messages = mock.MagicMock()
        received_messages.received_messages = [queue_message]
        self.gcp_consumer.subscriber.pull = mock.MagicMock(return_value=received_messages)
        self.gcp_consumer.process_message = mock.MagicMock(wraps=self.gcp_consumer.process_message)
        self.gcp_consumer.message_handler = mock.MagicMock(wraps=self.gcp_consumer.message_handler)

        self.gcp_consumer.fetch_and_process_messages(num_messages, visibility_timeout)

        self.gcp_consumer.subscriber.pull.assert_called_once_with(
            mock_pubsub_v1.SubscriberClient.subscription_path.return_value,
            num_messages,
            retry=None,
            timeout=gcp_settings.GOOGLE_PUBSUB_READ_TIMEOUT_S,
        )
        self.gcp_consumer.process_message.assert_called_once_with(queue_message)
        self.gcp_consumer.message_handler.assert_called_once_with(
            queue_message.message.data.decode(), GoogleMetadata(queue_message.ack_id)
        )
        self.gcp_consumer.subscriber.acknowledge.assert_called_once_with(
            mock_pubsub_v1.SubscriberClient.subscription_path.return_value, [queue_message.ack_id]
        )
        pre_process_hook.assert_called_once_with(google_pubsub_message=queue_message)
        post_process_hook.assert_called_once_with(google_pubsub_message=queue_message)

    def test_message_moved_to_dlq(self, mock_pubsub_v1, retry_once_settings, message):
        queue_message = self._build_gcp_queue_message(message)
        self.gcp_consumer.pull_messages = mock.MagicMock(return_value=[queue_message])
        self.gcp_consumer.message_handler = mock.MagicMock(side_effect=Exception)

        self.gcp_consumer.fetch_and_process_messages()

        self.gcp_consumer._publisher.publish.assert_called_once_with(
            self.gcp_consumer._dlq_topic_path, queue_message.message.data, **message.headers
        )

    def test_message_not_moved_to_dlq(self, mock_pubsub_v1, gcp_settings, message):
        queue_message = self._build_gcp_queue_message(message)
        self.gcp_consumer.pull_messages = mock.MagicMock(return_value=[queue_message])
        self.gcp_consumer.message_handler = mock.MagicMock(side_effect=Exception)

        self.gcp_consumer.fetch_and_process_messages()

        self.gcp_consumer._publisher.publish.assert_not_called()
