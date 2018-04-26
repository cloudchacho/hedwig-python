import json
from unittest import mock

from hedwig.consumer import get_default_queue_name
from hedwig import requeue_dead_letter


@mock.patch('hedwig.commands.get_queue_messages', autospec=True)
@mock.patch('hedwig.commands.get_queue', autospec=True)
def test_requeue_dead_letter(mock_get_queue, mock_get_queue_messages):
    num_messages = 3
    visibility_timeout = 4

    messages = [mock.MagicMock() for _ in range(num_messages)]
    mock_get_queue_messages.side_effect = iter([messages, None])
    dlq_name = f'{get_default_queue_name()}-DLQ'

    mock_queue, mock_dlq = mock.MagicMock(), mock.MagicMock()
    mock_queue.attributes = {'RedrivePolicy': json.dumps({'deadLetterTargetArn': dlq_name})}
    mock_queue.send_messages.return_value = {'Failed': []}
    mock_get_queue.side_effect = iter([mock_queue, mock_dlq])
    mock_dlq.delete_messages.return_value = {'Failed': []}

    requeue_dead_letter(num_messages, visibility_timeout)

    mock_get_queue.assert_has_calls([
        mock.call(get_default_queue_name()),
        mock.call(dlq_name),
    ])

    mock_get_queue_messages.assert_has_calls([
        mock.call(mock_dlq, num_messages=num_messages, visibility_timeout=visibility_timeout, wait_timeout_s=1),
        mock.call(mock_dlq, num_messages=num_messages, visibility_timeout=visibility_timeout, wait_timeout_s=1),
    ])

    mock_queue.send_messages.assert_called_once_with(
        Entries=[
            {
                'Id': queue_message.message_id,
                'MessageBody': queue_message.body,
                'MessageAttributes': queue_message.message_attributes
            }
            for queue_message in messages
        ]
    )

    mock_dlq.delete_messages.assert_called_once_with(
        Entries=[
            {
                'Id': queue_message.message_id,
                'ReceiptHandle': queue_message.receipt_handle,
            }
            for queue_message in messages
        ]
    )
