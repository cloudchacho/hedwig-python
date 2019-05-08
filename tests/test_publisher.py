from unittest import mock

from hedwig.publisher import publish


@mock.patch('hedwig.publisher.get_publisher_backend', autospec=True)
def test_publish(mock_get_publisher_backend, message):
    publish(message)

    mock_get_publisher_backend.assert_called_once_with()
    mock_get_publisher_backend.return_value.publish.assert_called_once_with(message)
