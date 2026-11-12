import re

import pytest


@pytest.fixture(autouse=True, scope="module")
def setup_instrumentation():
    from hedwig.instrumentation.compat import set_global_textmap
    import opentelemetry.trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.trace import set_tracer_provider
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    from opentelemetry.version import __version__

    otel_1_6_or_later = tuple(int(part) for part in re.findall(r"\d+", __version__)[:2]) >= (1, 6)

    try:
        # might already be set to default tracer provider
        opentelemetry.trace._TRACER_PROVIDER = None
        if otel_1_6_or_later:
            opentelemetry.trace._TRACER_PROVIDER_SET_ONCE._done = False

        set_tracer_provider(TracerProvider())

        set_global_textmap(TraceContextTextMapPropagator())

        yield
    finally:
        opentelemetry.trace._TRACER_PROVIDER = None
        if otel_1_6_or_later:
            opentelemetry.trace._TRACER_PROVIDER_SET_ONCE._done = False
