import logging
from unittest import mock

import pytest
from moto import mock_sqs, mock_sns

import hedwig.conf
from hedwig import models
from hedwig.backends import aws
from hedwig.backends.base import HedwigBaseBackend, HedwigPublisherBaseBackend
from hedwig.models import Message, MessageType
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


@pytest.fixture
def mock_boto3():
    settings.AWS_REGION = 'us-west-1'
    with mock_sqs(), mock_sns(), mock.patch("hedwig.backends.aws.boto3", autospec=True) as boto3_mock:
        yield boto3_mock


@pytest.fixture()
def sqs_consumer_backend(mock_boto3):
    yield aws.AWSSQSConsumerBackend()


@pytest.fixture
def mock_pubsub_v1():
    with mock.patch("hedwig.backends.gcp.pubsub_v1", autospec=True) as pubsub_v1_mock:
        yield pubsub_v1_mock


@pytest.fixture(params=["hedwig.backends.aws.AWSSQSConsumerBackend", "hedwig.backends.gcp.GooglePubSubConsumerBackend"])
def consumer_backend(request, mock_boto3):
    with mock.patch("hedwig.backends.gcp.pubsub_v1"):
        yield HedwigBaseBackend.build(request.param)


@pytest.fixture(
    params=["hedwig.backends.aws.AWSSNSConsumerBackend", "hedwig.backends.gcp.GooglePubSubPublisherBackend"]
)
def publisher_backend(request, mock_boto3):
    with mock.patch("hedwig.backends.gcp.pubsub_v1"):
        yield HedwigBaseBackend.build(request.param)


@pytest.fixture()
def mock_publisher_backend():
    with mock.patch.object(HedwigPublisherBaseBackend, '_publish'):
        yield HedwigPublisherBaseBackend()
