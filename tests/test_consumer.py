import threading
from unittest import mock

from hedwig.consumer import process_messages_for_lambda_consumer, listen_for_messages


@mock.patch('hedwig.consumer.get_consumer_backend', autospec=True)
def test_process_messages_for_lambda_consumer(mock_get_backend):
    event = mock.Mock()

    process_messages_for_lambda_consumer(event)

    mock_get_backend.assert_called_once_with()
    mock_get_backend.return_value.process_messages.assert_called_once_with(event)


@mock.patch('hedwig.consumer.get_consumer_backend', autospec=True)
class TestListenForMessages:
    def test_listen_for_messages(self, mock_get_backend):
        num_messages = 3
        visibility_timeout_s = 4
        shutdown_event = threading.Event()

        listen_for_messages(num_messages, visibility_timeout_s, shutdown_event=shutdown_event)

        mock_get_backend.assert_called_once_with()

        mock_get_backend.return_value.fetch_and_process_messages.assert_called_once_with(
            shutdown_event=shutdown_event, num_messages=num_messages, visibility_timeout=visibility_timeout_s
        )
