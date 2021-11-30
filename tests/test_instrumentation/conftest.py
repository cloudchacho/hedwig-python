import pytest


@pytest.fixture(autouse=True, scope="session")
def setup_instrumentation():
    from hedwig.instrumentation.compat import set_global_textmap
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.trace import set_tracer_provider
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

    set_tracer_provider(TracerProvider())

    set_global_textmap(TraceContextTextMapPropagator())
