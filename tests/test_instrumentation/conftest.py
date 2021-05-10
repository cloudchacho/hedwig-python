import pytest


@pytest.fixture(autouse=True, scope="module")
def setup_instrumentation():
    from hedwig.instrumentation.compat import set_global_textmap
    import opentelemetry.trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.trace import set_tracer_provider
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

    try:
        # might already be set to default tracer provider
        opentelemetry.trace._TRACER_PROVIDER = None

        set_tracer_provider(TracerProvider())

        set_global_textmap(TraceContextTextMapPropagator())

        yield
    finally:
        opentelemetry.trace._TRACER_PROVIDER = None
