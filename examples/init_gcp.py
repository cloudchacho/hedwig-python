import logging
import os
from logging import Formatter
from typing import Tuple

import structlog
from hedwig.instrumentation.compat import get_hexadecimal_trace_id, get_hexadecimal_span_id, set_global_textmap
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import set_tracer_provider, get_current_span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from examples import base_settings, example_gcp_settings


def init():
    os.environ.setdefault("SETTINGS_MODULE", "example_gcp_settings")

    setup_logging(base_settings.LOG_LEVEL)

    set_tracer_provider(TracerProvider())

    set_global_textmap(TraceContextTextMapPropagator())


def reset_root_logger():
    root = logging.getLogger()
    for handler in root.handlers[:]:
        # Copied from `logging.shutdown`.
        try:
            handler.acquire()
            handler.flush()
            handler.close()
        except (OSError, ValueError):
            pass
        finally:
            handler.release()
        root.removeHandler(handler)


def _get_current_cloud_trace_context() -> Tuple[str, str]:
    context = get_current_span().get_span_context()
    return (
        get_hexadecimal_trace_id(context.trace_id),
        get_hexadecimal_span_id(context.span_id),
    )


class StackdriverRenderer(structlog.processors.JSONRenderer):
    """
    Render the `event_dict` using with appropriate keys renamed as suitable for Stackdriver
    See https://cloud.google.com/run/docs/logging#log-resource for more details
    """

    def __call__(self, logger, name, event_dict):
        event_dict = {
            "severity": event_dict.pop("level").upper(),
            "message": event_dict.pop("event", ""),
            **event_dict,
        }
        if "stack" in event_dict:
            event_dict["stack_trace"] = event_dict.pop("stack")
        elif "exception" in event_dict:
            event_dict["stack_trace"] = event_dict.pop("exception")
        trace_id, span_id = _get_current_cloud_trace_context()
        # Add log correlation to nest all log messages
        # beneath request log in Log Viewer.
        event_dict["logging.googleapis.com/trace"] = (
            f"projects/{example_gcp_settings.GOOGLE_CLOUD_PROJECT}/traces/{trace_id}"
        )
        event_dict["logging.googleapis.com/spanId"] = span_id
        return super().__call__(logger, name, event_dict)


def setup_logging(log_level: str = "INFO") -> None:
    # Logging setup
    # Configure struct log
    timestamper = structlog.processors.TimeStamper(fmt=Formatter.default_time_format, utc=False)
    shared_processors = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    structlog_only_processors = [
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]
    structlog.configure(
        processors=shared_processors + structlog_only_processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure Python logging
    root = logging.getLogger()
    reset_root_logger()
    processor = StackdriverRenderer()
    formatter = structlog.stdlib.ProcessorFormatter(processor=processor, foreign_pre_chain=shared_processors)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level))
