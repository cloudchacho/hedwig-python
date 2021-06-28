import logging
from typing import Optional, Dict, Any

try:
    import structlog
except ImportError:  # pragma: no cover
    structlog = None  # type: ignore


def log(module: str, level: int, message: str, exc_info: Optional[bool] = None, extra: Optional[Dict[Any, Any]] = None):
    kwargs: Dict[Any, Any] = {}
    if exc_info is not None:
        kwargs["exc_info"] = True
    if structlog:
        method_name = logging.getLevelName(level).lower()
        if extra:
            kwargs.update(extra)
        logger = structlog.getLogger(module)
        method = getattr(logger, method_name)
        method(message, **kwargs)
    else:
        if extra:
            kwargs["extra"] = extra
        logging.getLogger(module).log(level, message, **kwargs)
