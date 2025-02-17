from contextlib import contextmanager
from typing import Dict, Iterator

from opentelemetry import trace
from opentelemetry.trace import Span

from hedwig.instrumentation.compat import Getter, extract, inject
from hedwig.models import Message

getter = Getter()


@contextmanager
def on_receive(attributes: dict) -> Iterator[Span]:
    """
    Hook for instrumenting consumer after message is dequeued. If applicable, starts a new span.
    :param attributes: Message attributes received from the backend, this is used to extract trace context.
    :return:
    """
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
