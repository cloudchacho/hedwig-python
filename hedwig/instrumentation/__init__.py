from contextlib import contextmanager
from typing import Dict, Optional, Iterator

from opentelemetry import trace
from opentelemetry.trace import Span

from hedwig.instrumentation.compat import Getter, extract, inject
from hedwig.models import Message

getter = Getter()


@contextmanager
def on_receive(sns_record=None, sqs_queue_message=None, google_pubsub_message=None) -> Iterator[Span]:
    """
    Hook for instrumenting consumer after message is dequeued. If applicable, starts a new span.
    :param sns_record:
    :param sqs_queue_message:
    :param google_pubsub_message:
    :return:
    """
    attributes: Optional[Dict]
    if sqs_queue_message is not None:
        attributes = {k: v["StringValue"] for k, v in sqs_queue_message.message_attributes.items()}
    elif sns_record is not None:
        attributes = sns_record["attributes"]
    elif google_pubsub_message is not None:
        attributes = google_pubsub_message.attributes
    else:
        attributes = None
    tracectx = extract(getter, attributes)  # type: ignore

    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("message_received", context=tracectx, kind=trace.SpanKind.CONSUMER) as span:
        yield span


def on_message(message: Message) -> None:
    """
    Hook for instrumenting consumer after message is deserialized and validated. If applicable, updates the current span
    with the right name.
    :param message:
    :return:
    """
    span = trace.get_current_span()
    span.update_name(message.type)


@contextmanager
def on_publish(message: Message, headers: Dict) -> Iterator[Span]:
    """
    Hook for instrumenting publish. If applicable, injects tracing headers into headers dictionary.
    :param message:
    :param headers:
    :return:
    """
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span(f"publish/{message.type}", kind=trace.SpanKind.PRODUCER) as span:
        inject(dict.__setitem__, headers)
        yield span
