from unittest import mock

from hedwig.commands import requeue_dead_letter


@mock.patch('hedwig.commands.get_consumer_backend', autospec=True)
def test_requeue_dead_letter(mock_get_consumer_backend):
    requeue_dead_letter()
    mock_get_consumer_backend.assert_called_once_with(dlq=True)
    mock_get_consumer_backend.return_value.requeue_dead_letter.assert_called_once_with(10, None)
