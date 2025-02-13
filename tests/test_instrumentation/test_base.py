from unittest import mock

import pytest

get_tracer = pytest.importorskip('opentelemetry.trace').get_tracer


@mock.patch('hedwig.backends.base.Message.exec_callback', autospec=True)
def test_message_handler_updates_span_name(mock_exec_callback, message, consumer_backend):
    provider_metadata = mock.Mock()
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span(test_message_handler_updates_span_name.__name__, {}) as span:
        assert span.name == test_message_handler_updates_span_name.__name__
        consumer_backend.message_handler(*message.serialize(), provider_metadata)
        assert span.name == message.type
        assert span.get_span_context().is_valid
