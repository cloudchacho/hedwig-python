import os
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Generator

from hedwig.conf import settings


@contextmanager
def override_env(env: str, value: Any) -> Generator[None, None, None]:
    """
    Override environment variable value temporarily
    """
    orig_value = os.environ.get(env)

    os.environ[env] = value

    try:
        yield
    finally:
        # was the value originally set? if so, restore it
        if orig_value is not None:
            os.environ[env] = orig_value
        else:
            # value wasn't set originally, so unset it again
            del os.environ[env]


@lru_cache(maxsize=3)
def get_publisher_backend(*args, **kwargs):
    return settings.HEDWIG_PUBLISHER_BACKEND(*args, **kwargs)


@lru_cache(maxsize=3)
def get_consumer_backend(*args, **kwargs):
    return settings.HEDWIG_CONSUMER_BACKEND(*args, **kwargs)
