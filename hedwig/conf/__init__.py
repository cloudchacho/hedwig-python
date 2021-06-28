#!/usr/bin/env python
import logging
import os
import importlib
import typing

from hedwig.backends.import_utils import import_module_attr
from hedwig.utils import log

try:
    from django.conf import settings as django_settings
    from django.dispatch import receiver
    from django.test import signals

    HAVE_DJANGO = True  # pragma: no cover
except ImportError:
    HAVE_DJANGO = False

try:
    from flask import current_app  # pragma: no cover

    HAVE_FLASK = True  # pragma: no cover
except ImportError:
    HAVE_FLASK = False

_DEFAULTS: dict = {
    'AWS_REGION': None,
    'AWS_ACCOUNT_ID': None,
    'AWS_ACCESS_KEY': None,
    'AWS_CONNECT_TIMEOUT_S': 2,
    'AWS_ENDPOINT_SNS': None,
    'AWS_ENDPOINT_SQS': None,
    'AWS_READ_TIMEOUT_S': 2,
    'AWS_SECRET_KEY': None,
    'AWS_SESSION_TOKEN': None,
    'GOOGLE_APPLICATION_CREDENTIALS': None,
    'GOOGLE_CLOUD_PROJECT': None,
    'GOOGLE_PUBSUB_READ_TIMEOUT_S': 5,
    'HEDWIG_CALLBACKS': {},
    'HEDWIG_CONSUMER_BACKEND': None,
    'HEDWIG_DATA_VALIDATOR_CLASS': 'hedwig.validators.jsonschema.JSONSchemaValidator',
    'HEDWIG_DEFAULT_HEADERS': 'hedwig.conf.default_headers_hook',
    'HEDWIG_MESSAGE_ROUTING': {},
    'HEDWIG_PRE_PROCESS_HOOK': 'hedwig.conf.noop_hook',
    'HEDWIG_POST_PROCESS_HOOK': 'hedwig.conf.noop_hook',
    'HEDWIG_PUBLISHER': None,
    'HEDWIG_PUBLISHER_BACKEND': None,
    'HEDWIG_PUBLISHER_GCP_BATCH_SETTINGS': (),
    'HEDWIG_QUEUE': None,
    'HEDWIG_JSONSCHEMA_FILE': None,
    'HEDWIG_PROTOBUF_MESSAGES': None,
    'HEDWIG_SYNC': False,
    'HEDWIG_SUBSCRIPTIONS': [],
    'HEDWIG_USE_TRANSPORT_MESSAGE_ATTRIBUTES': True,
}


# List of settings that may be in string import notation.
_IMPORT_STRINGS = (
    'HEDWIG_CONSUMER_BACKEND',
    'HEDWIG_DATA_VALIDATOR_CLASS',
    'HEDWIG_DEFAULT_HEADERS',
    'HEDWIG_PRE_PROCESS_HOOK',
    'HEDWIG_POST_PROCESS_HOOK',
    'HEDWIG_PUBLISHER_BACKEND',
)

# List of settings that will be dicts with values as string import notation.
_IMPORT_DICT_VALUES = ('HEDWIG_CALLBACKS',)

# List of settings that will be lists with values as string import notation.
_IMPORT_LIST_VALUES = ('HEDWIG_PROTOBUF_MESSAGES',)


def default_headers_hook(*args, **kwargs) -> typing.Dict[str, str]:
    return {}


def noop_hook(*args, **kwargs) -> None:
    pass


class _LazySettings:
    """
    A lazy object, that allows settings to be accessed as properties.
    For example:

    .. code-block:: python

        from hedwig.conf import settings
        print(settings.AWS_REGION)

    Any setting with string import paths will be automatically resolved
    and return the class, rather than the string literal.
    """

    def __init__(self) -> None:
        self._defaults = _DEFAULTS
        self._import_strings = _IMPORT_STRINGS
        self._import_dict_values = _IMPORT_DICT_VALUES
        self._import_list_values = _IMPORT_LIST_VALUES
        self._user_settings: object = None

    @property
    def configured(self) -> bool:
        """
        Have Hedwig settings been configured?
        """
        return bool(self._user_settings)

    def _ensure_configured(self):
        if self.configured:
            return

        if os.environ.get("SETTINGS_MODULE"):
            log(__name__, logging.INFO, f'Configuring Hedwig through module: {os.environ["SETTINGS_MODULE"]}')
            self._user_settings = importlib.import_module(os.environ["SETTINGS_MODULE"], package=None)
        elif HAVE_DJANGO:  # pragma: no cover
            log(__name__, logging.INFO, 'Configuring Hedwig through django settings')
            # automatically import Django settings in Django projects
            self._user_settings = django_settings
        elif HAVE_FLASK:  # pragma: no cover
            log(__name__, logging.INFO, 'Configuring Hedwig through flask settings')
            # automatically import Flask settings in Flask projects
            self._user_settings = current_app.config
        if not self._user_settings:
            raise ImportError("Hedwig settings have not been configured")

    def configure_with_object(self, obj: object) -> None:  # pragma: no cover
        """
        Set Hedwig config using a dataclass-like object that contains all settings as its attributes, or a dict that
        contains settings as its keys.
        """
        assert not self._user_settings, "Hedwig settings have already been configured"

        log(__name__, logging.INFO, 'Configuring Hedwig through object')
        self._user_settings = obj

    @staticmethod
    def _import_string(
        dotted_path_or_callable: typing.Union[typing.Callable, str]
    ) -> typing.Union[typing.Callable, typing.Type]:
        """
        Import a dotted module path and return the attribute/class designated by the
        last name in the path. Raise ImportError if the import failed.
        """
        if callable(dotted_path_or_callable):
            return dotted_path_or_callable

        return import_module_attr(dotted_path_or_callable)

    def _get_setting_from_object(self, attr: str):
        if isinstance(self._user_settings, dict):  # pragma: no cover
            if attr in self._user_settings:
                return self._user_settings[attr]
            elif attr.lower() in self._user_settings:
                return self._user_settings[attr.lower()]
            raise RuntimeError
        else:
            try:
                # Check if present in user settings
                return getattr(self._user_settings, attr)
            except AttributeError:
                # try lowercase
                try:
                    return getattr(self._user_settings, attr.lower())
                except AttributeError:
                    raise RuntimeError

    def __getattr__(self, attr: str) -> typing.Any:
        self._ensure_configured()

        if attr not in self._defaults:
            raise AttributeError("Invalid setting: '%s'" % attr)

        try:
            val = self._get_setting_from_object(attr)
        except RuntimeError:
            # Fall back to defaults
            val = self._defaults[attr]

        # Coerce import strings into classes
        if attr in self._import_strings:
            val = self._import_string(val)

        if attr in self._import_dict_values:
            val = {k: self._import_string(v) for k, v in val.items()}

        if attr in self._import_list_values:
            val = [self._import_string(v) for v in val]

        # Cache the result
        setattr(self, attr, val)
        return val

    def clear_cache(self) -> None:
        """
        Clear settings cache - useful for testing only
        """
        from hedwig.backends.utils import get_publisher_backend, get_consumer_backend
        from hedwig.callback import Callback
        from hedwig.models import _validator

        for attr in self._defaults:
            try:
                delattr(self, attr)
            except AttributeError:
                pass
        Callback.find_by_message.cache_clear()

        # since consumer/publisher settings may have changed
        get_publisher_backend.cache_clear()
        get_consumer_backend.cache_clear()

        # in case a test overrides HEDWIG_DATA_VALIDATOR_CLASS
        _validator.cache_clear()


if HAVE_DJANGO:  # pragma: no cover

    @receiver(signals.setting_changed)
    def clear_cache_on_setting_override(sender, setting, value, enter, **kwargs):
        settings.clear_cache()


settings = _LazySettings()
"""
This object allows settings to be accessed as properties. Settings can be configured in one of three ways:

#. Environment variable named ``SETTINGS_MODULE`` that points to a python module with settings as module attributes

#. Django - if Django can be imported, Django settings will be used automatically

#. Using an object or dict, by calling :meth:`hedwig.conf.settings.configure_with_object`

Some setting values need to be string import paths will be automatically resolved and return the class.

Once settings have been configured, they shouldn't be changed. It is possible to re-configure for testing, but its not
guaranteed to work the same way for non-test use cases.
"""
