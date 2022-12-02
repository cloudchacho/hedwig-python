from distutils.version import StrictVersion

from opentelemetry.version import __version__

VERSION_1_0_0 = StrictVersion("1.0.0")

if StrictVersion(__version__) >= VERSION_1_0_0:
    from opentelemetry.propagate import extract as extract_10, inject as inject_10  # type: ignore
    from opentelemetry.propagators.textmap import DefaultGetter as Getter  # type: ignore
    from opentelemetry.trace.span import (
        format_trace_id as get_hexadecimal_trace_id,
        format_span_id as get_hexadecimal_span_id,
    )
    from opentelemetry.propagate import set_global_textmap

    id_generator_class = "opentelemetry.sdk.trace.RandomIdGenerator"

    def get_traceparent_string(trace_id, span_id, trace_flags):
        return "00-{trace_id}-{span_id}-{:02x}".format(
            trace_flags,
            trace_id=get_hexadecimal_trace_id(trace_id),
            span_id=get_hexadecimal_span_id(span_id),
        )

else:
    from opentelemetry.propagators import extract, inject  # type: ignore
    from opentelemetry.trace.propagation.textmap import DictGetter as Getter  # type: ignore
    from opentelemetry.trace.span import get_hexadecimal_trace_id, get_hexadecimal_span_id
    from opentelemetry.propagators import set_global_textmap

    id_generator_class = "opentelemetry.sdk.trace.RandomIdsGenerator"

    def get_traceparent_string(trace_id, span_id, trace_flags):
        return "00-{:032x}-{:016x}-{:02x}".format(
            trace_id,
            span_id,
            trace_flags,
        )


if StrictVersion(__version__) >= VERSION_1_0_0:

    def extract(getter, carrier):  # type: ignore
        return extract_10(carrier)

    def inject(setter, carrier):  # type: ignore
        return inject_10(carrier)


__ALL__ = [
    "Getter",
    "extract",
    "get_hexadecimal_span_id",
    "get_hexadecimal_trace_id",
    "id_generator_class",
    "inject",
    "set_global_textmap",
]
