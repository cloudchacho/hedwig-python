#!/usr/bin/env python
import logging
import os
import importlib
import typing
from copy import deepcopy

try:
    from django.conf import settings as django_settings
    from django.dispatch import receiver
    from django.test import signals

    HAVE_DJANGO = True
except ImportError:
    HAVE_DJANGO = False


_DEFAULTS = {
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
    'HEDWIG_DATA_VALIDATOR_CLASS': 'hedwig.validator.MessageValidator',
    'HEDWIG_DEFAULT_HEADERS': 'hedwig.conf.default_headers_hook',
    'HEDWIG_DLQ_TOPIC': None,
    'HEDWIG_GOOGLE_MESSAGE_RETRY_STATE_BACKEND': None,
    'HEDWIG_GOOGLE_MESSAGE_RETRY_STATE_REDIS_URL': None,
    'HEDWIG_GOOGLE_MESSAGE_MAX_RETRIES': 3,
    'HEDWIG_MESSAGE_ROUTING': {},
    'HEDWIG_POST_DESERIALIZE_HOOK': 'hedwig.conf.noop_hook',
    'HEDWIG_PRE_PROCESS_HOOK': 'hedwig.conf.noop_hook',
    'HEDWIG_POST_PROCESS_HOOK': 'hedwig.conf.noop_hook',
    'HEDWIG_PRE_SERIALIZE_HOOK': 'hedwig.conf.noop_hook',
    'HEDWIG_PUBLISHER': None,
    'HEDWIG_PUBLISHER_BACKEND': None,
    'HEDWIG_PUBLISHER_GCP_BATCH_SETTINGS': (),
    'HEDWIG_QUEUE': None,
    'HEDWIG_SCHEMA_FILE': None,
    'HEDWIG_SYNC': False,
    'HEDWIG_SUBSCRIPTIONS': [],
}


# List of settings that may be in string import notation.
_IMPORT_STRINGS = (
    'HEDWIG_DATA_VALIDATOR_CLASS',
    'HEDWIG_DEFAULT_HEADERS',
    'HEDWIG_POST_DESERIALIZE_HOOK',
    'HEDWIG_PRE_PROCESS_HOOK',
    'HEDWIG_POST_PROCESS_HOOK',
    'HEDWIG_PRE_SERIALIZE_HOOK',
)

# List of settings that will be dicts with values as string import notation.
_IMPORT_DICT_VALUES = ('HEDWIG_CALLBACKS',)


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
            logging.info(f'Configuring Hedwig through module: {os.environ["SETTINGS_MODULE"]}')
            self._user_settings = importlib.import_module(os.environ["SETTINGS_MODULE"], package=None)
        elif HAVE_DJANGO:
            logging.info('Configuring Hedwig through django settings')
            # automatically import Django settings in Django projects
            self._user_settings = django_settings
        if not self._user_settings:
            raise ImportError("Hedwig settings have not been configured")

    def configure_with_object(self, obj: object) -> None:
        """
        Set Hedwig config using a dataclass-like object that contains all settings as it's attributes.
        """
        assert not self._user_settings, "Hedwig settings have already been configured"

        logging.info('Configuring Hedwig through object')
        self._user_settings = deepcopy(obj)

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

        try:
            module_path, class_name = dotted_path_or_callable.rsplit('.', 1)
        except ValueError as err:
            raise ImportError(f"{dotted_path_or_callable} doesn't look like a module path") from err

        module = importlib.import_module(module_path)

        try:
            return getattr(module, class_name)
        except AttributeError as err:
            raise ImportError(f"Module '{module_path}' does not define a '{class_name}' attribute/class") from err

    def __getattr__(self, attr: str) -> typing.Any:
        self._ensure_configured()

        if attr not in self._defaults:
            raise AttributeError("Invalid API setting: '%s'" % attr)

        try:
            # Check if present in user settings
            val = getattr(self._user_settings, attr)
        except AttributeError:
            # try lowercase
            try:
                val = getattr(self._user_settings, attr.lower())
            except AttributeError:
                # Fall back to defaults
                val = self._defaults[attr]

        # Coerce import strings into classes
        if attr in self._import_strings:
            val = self._import_string(val)

        if attr in self._import_dict_values:
            val = {k: self._import_string(v) for k, v in val.items()}

        # Cache the result
        setattr(self, attr, val)
        return val

    def clear_cache(self) -> None:
        """
        Clear settings cache - useful for testing only
        """
        for attr in self._defaults:
            try:
                delattr(self, attr)
            except AttributeError:
                pass


if HAVE_DJANGO:

    @receiver(signals.setting_changed)
    def clear_cache_on_setting_override(sender, setting, value, enter, **kwargs):
        settings.clear_cache()


settings = _LazySettings()
"""
This object allows settings to be accessed as properties. Settings can be configured in one of three ways:

#. Environment variable named ``SETTINGS_MODULE`` that points to a python module with settings as module attributes

#. Django - if Django can be imported, Django settings will be used automatically

#. Using an object, by calling :meth:`hedwig.conf.settings.configure_with_object`

Some setting values need to be string import paths will be automatically resolved and return the class.

Once settings have been configured, they can't be changed.
"""
