import base64
import random
import threading
from datetime import datetime, timezone
from unittest import mock

import pytest

from hedwig.conf import settings as hedwig_settings

try:
    from opentelemetry.trace import get_current_span, get_tracer
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

    from hedwig.backends.aws import AWSMetadata
    from hedwig.instrumentation.compat import get_hexadecimal_trace_id, id_generator_class, get_traceparent_string
except ImportError:
    pass

from tests.utils.mock import mock_return_once

aws = pytest.importorskip('hedwig.backends.aws')
instrumentation = pytest.importorskip('hedwig.instrumentation')


@pytest.fixture(name='sqs_consumer')
def _sqs_consumer(mock_boto3):
    return aws.AWSSQSConsumerBackend()


def test_fetch_and_process_message_follows_parent_trace(
    sqs_consumer,
    message_with_trace,
    use_transport_message_attrs,
):
    shutdown_event = threading.Event()
    num_messages = 3
    visibility_timeout = 4
    queue = mock.MagicMock()
    sqs_consumer.sqs_resource.get_queue_by_name = mock.MagicMock(return_value=queue)

    receipt = "receipt"
    sent_time = datetime.now(timezone.utc)
    first_receive_time = datetime.now(timezone.utc)
    receive_count = 1

    queue_message = mock.MagicMock()
    queue_message.receipt_handle = receipt
    payload, message_attributes = message_with_trace.serialize()
    if isinstance(payload, bytes):
        queue_message.body = base64.encodebytes(payload).decode()
        message_attributes['hedwig_encoding'] = 'base64'
    else:
        queue_message.body = payload
    queue_message.message_attributes = {
        k: {'DataType': 'String', 'StringValue': v} for k, v in message_attributes.items()
    }
    queue_message.attributes = {
        'ApproximateReceiveCount': receive_count,
        'SentTimestamp': int(sent_time.timestamp() * 1000),
        'ApproximateFirstReceiveTimestamp': int(first_receive_time.timestamp() * 1000),
    }

    def verify_span(*args, **kwargs):
        span = get_current_span()
        assert span.get_span_context().is_valid
        assert (
            get_hexadecimal_trace_id(span.get_span_context().trace_id)
            == message_with_trace.headers["traceparent"].split("-")[1]
        )
        return mock.DEFAULT

    mock_return_once(queue.receive_messages, [queue_message], [], shutdown_event)
    message_mock = mock.MagicMock()
    sqs_consumer._build_message = mock.MagicMock(return_value=message_mock)
    sqs_consumer.process_message = mock.MagicMock(wraps=sqs_consumer.process_message, side_effect=verify_span)
    sqs_consumer.message_handler = mock.MagicMock(wraps=sqs_consumer.message_handler)

    sqs_consumer.fetch_and_process_messages(num_messages, visibility_timeout, shutdown_event)

    sqs_consumer.sqs_resource.get_queue_by_name.assert_called_with(QueueName=sqs_consumer.queue_name)
    queue.receive_messages.assert_called_with(
        MaxNumberOfMessages=num_messages,
        MessageAttributeNames=['All'],
        AttributeNames=['All'],
        VisibilityTimeout=visibility_timeout,
        WaitTimeSeconds=sqs_consumer.WAIT_TIME_SECONDS,
    )
    sqs_consumer.process_message.assert_called_once_with(queue_message)
    sqs_consumer.message_handler.assert_called_once_with(
        payload,
        message_attributes,
        AWSMetadata(
            receipt,
            # truncates to millisecond precision
            first_receive_time.replace(microsecond=(first_receive_time.microsecond // 1000) * 1000),
            sent_time.replace(microsecond=(sent_time.microsecond // 1000) * 1000),
            receive_count,
        ),
    )
    message_mock.exec_callback.assert_called_once_with()
    queue_message.delete.assert_called_once_with()


def test_publish_sends_trace_id(mock_boto3, message, use_transport_message_attrs):
    sns_publisher = aws.AWSSNSPublisherBackend()
    queue = mock.MagicMock()
    sns_publisher.sns_client.publish.get_queue_by_name = mock.MagicMock(return_value=queue)

    span_id = random.getrandbits(64)

    tracer = get_tracer(__name__)
    with tracer.start_as_current_span(test_publish_sends_trace_id.__name__), mock.patch(
        f"{id_generator_class}.generate_span_id", return_value=span_id
    ):
        trace_id = get_current_span().get_span_context().trace_id
        sns_publisher.publish(message)

    mock_boto3.client.assert_called_once_with(
        'sns',
        region_name=hedwig_settings.AWS_REGION,
        aws_access_key_id=hedwig_settings.AWS_ACCESS_KEY,
        aws_secret_access_key=hedwig_settings.AWS_SECRET_KEY,
        aws_session_token=hedwig_settings.AWS_SESSION_TOKEN,
        endpoint_url=hedwig_settings.AWS_ENDPOINT_SQS,
        config=mock.ANY,
    )
    topic = sns_publisher._get_sns_topic(message)
    traceparent_string = get_traceparent_string(trace_id, span_id, 1)
    instrumentation_headers = {TraceContextTextMapPropagator._TRACEPARENT_HEADER_NAME: traceparent_string}
    message = message.with_headers({**message.headers, **instrumentation_headers})
    data, attrs = message.serialize()
    if not use_transport_message_attrs:
        attrs = message.headers
    if isinstance(data, bytes):
        data = base64.encodebytes(data).decode()
        attrs['hedwig_encoding'] = 'base64'
    sns_publisher.sns_client.publish.assert_called_once_with(
        TopicArn=topic,
        Message=data,
        MessageAttributes={k: {'DataType': 'String', 'StringValue': str(v)} for k, v in attrs.items()},
    )
