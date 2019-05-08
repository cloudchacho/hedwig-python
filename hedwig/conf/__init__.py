#!/usr/bin/env python

import os
import importlib
import typing

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
    'GOOGLE_PUBSUB_PROJECT_ID': None,
    'GOOGLE_PUBSUB_READ_TIMEOUT_S': 5,
    'HEDWIG_CALLBACKS': {},
    'HEDWIG_CONSUMER_BACKEND': None,
    'HEDWIG_DATA_VALIDATOR_CLASS': 'hedwig.validator.MessageValidator',
    'HEDWIG_DEFAULT_HEADERS': 'hedwig.conf.default_headers_hook',
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
    A settings object, that allows settings to be accessed as properties.
    For example:
        from hedwig.conf import settings
        print(settings.AWS_REGION)
    Any setting with string import paths will be automatically resolved
    and return the class, rather than the string literal.
    """

    def __init__(self) -> None:
        self._defaults = _DEFAULTS
        self._import_strings = _IMPORT_STRINGS
        self._import_dict_values = _IMPORT_DICT_VALUES
        self._user_settings = None

        if os.environ.get("SETTINGS_MODULE"):
            self._user_settings = importlib.import_module(os.environ["SETTINGS_MODULE"], package=None)
        elif HAVE_DJANGO:
            # automatically import Django settings in Django projects
            self._user_settings = django_settings
        else:
            raise ImportError("No settings module found to import")

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
        if attr not in self._defaults:
            raise AttributeError("Invalid API setting: '%s'" % attr)

        try:
            # Check if present in user settings
            val = getattr(self._user_settings, attr)
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
