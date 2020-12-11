import logging
from typing import Optional, Dict, Any

try:
    import structlog
except ImportError:
    structlog = None


def log(module: str, level: int, message: str, exc_info: Optional[bool] = None, extra: Optional[Dict[Any, Any]] = None):
    kwargs: Dict[Any, Any] = {}
    if exc_info is not None:
        kwargs["exc_info"] = True
    if structlog:
        kwargs["level"] = logging.getLevelName(level).lower()
        if extra:
            kwargs.update(extra)
        structlog.getLogger(module).msg(message, **kwargs)
    else:
        if extra:
            kwargs["extra"] = extra
        logging.getLogger(module).log(level, message, **kwargs)
