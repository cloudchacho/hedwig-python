import logging

import pytest

from hedwig import Message, MessageType, models
import hedwig.conf
from hedwig.testing.factories import MessageFactory


def pytest_configure():
    logging.basicConfig()


@pytest.fixture
def settings():
    """
    Use this fixture to override settings. Changes are automatically reverted
    """
    overrides = {}
    original_module = hedwig.conf.settings._user_settings

    class Wrapped:
        def __getattr__(self, name):
            return overrides.get(name, getattr(original_module, name))

    hedwig.conf.settings._user_settings = Wrapped()
    hedwig.conf.settings.clear_cache()
    # in case a test overrides HEDWIG_DATA_VALIDATOR_CLASS
    models._validator = None

    try:
        yield hedwig.conf.settings._user_settings
    finally:
        hedwig.conf.settings._user_settings = original_module
        hedwig.conf.settings.clear_cache()
        # in case a test overrides HEDWIG_DATA_VALIDATOR_CLASS
        models._validator = None


@pytest.fixture(name='message_data')
def _message_data():
    return MessageFactory.build(msg_type=MessageType.trip_created)


@pytest.fixture()
def message(message_data):
    return Message(message_data)
