from unittest import mock

from hedwig.consumer import process_messages_for_lambda_consumer, listen_for_messages


@mock.patch('hedwig.consumer.AWSSNSConsumerBackend')
def test_process_messages_for_lambda_consumer(mock_consumer_backend_cls):
    records = mock.Mock(), mock.Mock()
    event = {'Records': records}
    process_messages_for_lambda_consumer(event)
    mock_consumer_backend_cls.assert_called_once_with()
    mock_consumer_backend_cls.return_value.process_message.assert_has_calls([mock.call(r) for r in records])


@mock.patch('hedwig.consumer.get_consumer_backend', autospec=True)
class TestListenForMessages:
    def test_listen_for_messages(self, mock_get_backend):
        num_messages = 3
        visibility_timeout_s = 4
        loop_count = 1

        listen_for_messages(num_messages, visibility_timeout_s, loop_count)

        mock_get_backend.assert_called_once_with()

        mock_get_backend.return_value.fetch_and_process_messages.assert_called_once_with(
            num_messages=num_messages, visibility_timeout=visibility_timeout_s
        )
