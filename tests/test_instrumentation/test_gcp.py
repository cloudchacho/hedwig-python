import random
import threading
from unittest import mock

import pytest

try:
    from opentelemetry.trace import get_current_span, get_tracer
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

    from hedwig.instrumentation.compat import get_hexadecimal_trace_id, id_generator_class, get_traceparent_string

    from tests.utils.gcp import build_gcp_queue_message
except ImportError:
    pass

gcp = pytest.importorskip('hedwig.backends.gcp')
instrumentation = pytest.importorskip('hedwig.instrumentation')


@pytest.fixture(name='subscription_paths')
def _subscription_paths(gcp_settings):
    return [mock.MagicMock() for _ in range(len(gcp_settings.HEDWIG_SUBSCRIPTIONS) + 1)]


@pytest.fixture(name='gcp_consumer')
def _gcp_consumer(mock_pubsub_v1, gcp_settings, subscription_paths):
    mock_pubsub_v1.SubscriberClient.subscription_path.side_effect = subscription_paths
    return gcp.GooglePubSubConsumerBackend()


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


def test_fetch_and_process_message_follows_parent_trace(
    gcp_consumer,
    message_with_trace,
    use_transport_message_attrs,
):
    shutdown_event = threading.Event()
    num_messages = 3
    visibility_timeout = 4

    queue_message = build_gcp_queue_message(message_with_trace)

    def subscribe_side_effect(subscription_path, callback, flow_control, scheduler):
        if gcp_consumer.subscriber.subscribe.call_count == 1:
            # send message
            scheduler.schedule(None, message=queue_message)

        shutdown_event.set()

        # return a "future"
        return mock.MagicMock()

    def verify_span(*args, **kwargs):
        curr_span = get_current_span()
        assert curr_span.get_span_context().is_valid
        assert (
            get_hexadecimal_trace_id(curr_span.get_span_context().trace_id)
            == message_with_trace.headers["traceparent"].split("-")[1]
        )
        return mock.DEFAULT

    gcp_consumer.subscriber.subscribe.side_effect = subscribe_side_effect
    gcp_consumer.process_message = mock.MagicMock(wraps=gcp_consumer.process_message, side_effect=verify_span)
    gcp_consumer.message_handler = mock.MagicMock(wraps=gcp_consumer.message_handler)

    gcp_consumer.fetch_and_process_messages(
        num_messages=num_messages, visibility_timeout=visibility_timeout, shutdown_event=shutdown_event
    )

    gcp_consumer.message_handler.assert_called_once()
    queue_message.ack.assert_called_once_with()


def test_publish_sends_trace_id(mock_pubsub_v1, message, gcp_settings, use_transport_message_attrs):
    gcp_publisher = gcp.GooglePubSubPublisherBackend()
    gcp_publisher.publisher.topic_path = mock.MagicMock(return_value="dummy_topic_path")

    span_id = random.getrandbits(64)

    tracer = get_tracer(__name__)
    with tracer.start_as_current_span(test_publish_sends_trace_id.__name__), mock.patch(
        f"{id_generator_class}.generate_span_id", return_value=span_id
    ):
        trace_id = get_current_span().get_span_context().trace_id
        message_id = gcp_publisher.publish(message)

    assert message_id == gcp_publisher.publisher.publish.return_value.result()

    traceparent_string = get_traceparent_string(trace_id, span_id, 1)
    instrumentation_headers = {TraceContextTextMapPropagator._TRACEPARENT_HEADER_NAME: traceparent_string}
    message = message.with_headers({**message.headers, **instrumentation_headers})
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
