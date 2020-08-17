import logging
from contextlib import contextmanager
from unittest import mock

import pytest

import hedwig.conf
from hedwig.backends.base import HedwigPublisherBaseBackend
from hedwig.backends.import_utils import import_module_attr
from hedwig.backends.utils import get_publisher_backend, get_consumer_backend
from hedwig.models import _validator
from hedwig.testing.factories import MessageFactory

from tests.models import MessageType

try:
    # may not be available
    from moto import mock_sqs, mock_sns
except ImportError:
    pass


def pytest_configure():
    logging.basicConfig()


@pytest.fixture
def settings():
    """
    Use this fixture to override settings. Changes are automatically reverted
    """
    original_module = hedwig.conf.settings._user_settings

    class Wrapped:
        # default to the original module, but allow tests to setattr which would override
        def __getattr__(self, name):
            return getattr(original_module, name)

    hedwig.conf.settings._user_settings = Wrapped()
    hedwig.conf.settings.clear_cache()

    # since consumer/publisher settings may have changed
    get_publisher_backend.cache_clear()
    get_consumer_backend.cache_clear()

    # in case a test overrides HEDWIG_DATA_VALIDATOR_CLASS
    _validator.cache_clear()

    try:
        yield hedwig.conf.settings._user_settings
    finally:
        hedwig.conf.settings._user_settings = original_module
        hedwig.conf.settings.clear_cache()

        # in case a test overrides HEDWIG_DATA_VALIDATOR_CLASS
        _validator.cache_clear()

        # since consumer/publisher settings may have changed
        get_publisher_backend.cache_clear()
        get_consumer_backend.cache_clear()


@pytest.fixture(name='message_data')
def _message_data():
    return MessageFactory.build(msg_type=MessageType.trip_created)


@pytest.fixture()
def message():
    return MessageFactory(msg_type=MessageType.trip_created)


@contextmanager
def _mock_boto3():
    settings.AWS_REGION = 'us-west-1'
    with mock_sqs(), mock_sns(), mock.patch("hedwig.backends.aws.boto3", autospec=True) as boto3_mock:
        yield boto3_mock


@pytest.fixture
def mock_boto3():
    with _mock_boto3() as m:
        yield m


@pytest.fixture()
def sqs_consumer_backend(mock_boto3):
    # may not be available
    from hedwig.backends import aws

    yield aws.AWSSQSConsumerBackend()


@pytest.fixture
def mock_pubsub_v1():
    with mock.patch("hedwig.backends.gcp.pubsub_v1", autospec=True) as pubsub_v1_mock:
        yield pubsub_v1_mock


@pytest.fixture(params=['aws', 'google'])
def consumer_backend(request):
    if request.param == 'aws':
        try:
            from hedwig.backends.aws import AWSSQSConsumerBackend  # noqa

            with _mock_boto3():
                yield AWSSQSConsumerBackend()
        except ImportError:
            pytest.skip("AWS backend not importable")

    if request.param == 'google':
        try:
            from hedwig.backends.gcp import GooglePubSubConsumerBackend  # noqa

            with mock.patch("hedwig.backends.gcp.pubsub_v1"), mock.patch(
                "hedwig.backends.gcp.google_auth_default", return_value=(None, "DUMMY")
            ):
                yield GooglePubSubConsumerBackend()
        except ImportError:
            pytest.skip("Google backend not importable")


@pytest.fixture(
    params=["hedwig.backends.aws.AWSSNSConsumerBackend", "hedwig.backends.gcp.GooglePubSubPublisherBackend"]
)
def publisher_backend(request, mock_boto3):
    with mock.patch("hedwig.backends.gcp.pubsub_v1"):
        yield import_module_attr(request.param)


@pytest.fixture()
def mock_publisher_backend():
    with mock.patch.object(HedwigPublisherBaseBackend, '_publish'):
        yield HedwigPublisherBaseBackend()


@pytest.fixture(params=[True, False], ids=["message-attrs", "no-message-attrs"])
def use_transport_message_attrs(request, settings):
    settings.HEDWIG_USE_TRANSPORT_MESSAGE_ATTRIBUTES = request.param
    yield settings.HEDWIG_USE_TRANSPORT_MESSAGE_ATTRIBUTES
