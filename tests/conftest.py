import logging
from contextlib import contextmanager
from unittest import mock

import pytest

import hedwig.conf
from hedwig.backends.import_utils import import_module_attr
from hedwig.testing.config import unconfigure
from tests import MockHedwigPublisherBackend

from tests.models import MessageType

try:
    # may not be available
    from moto import mock_aws
except ImportError:
    pass


def pytest_configure():
    logging.basicConfig()


@pytest.fixture
def settings():
    """
    Use this fixture to override settings. Changes are automatically reverted
    """
    hedwig.conf.settings._ensure_configured()
    original_module = hedwig.conf.settings._user_settings

    class Wrapped:
        # default to the original module, but allow tests to setattr which would override
        def __getattr__(self, name):
            return getattr(original_module, name)

    unconfigure()
    hedwig.conf.settings._user_settings = Wrapped()

    try:
        yield hedwig.conf.settings._user_settings
    finally:
        unconfigure()
        hedwig.conf.settings._user_settings = original_module


@pytest.fixture(name='message_factory', params=['jsonschema', 'protobuf'])
def _message_factory(request, settings):
    if request.param == 'jsonschema':
        settings.HEDWIG_DATA_VALIDATOR_CLASS = 'hedwig.validators.jsonschema.JSONSchemaValidator'

        try:
            import jsonschema  # noqa
            from hedwig.testing.factories.jsonschema import JSONSchemaMessageFactory  # noqa

            yield JSONSchemaMessageFactory
        except ImportError:
            pytest.skip("JSON Schema not importable")

    if request.param == 'protobuf':
        settings.HEDWIG_DATA_VALIDATOR_CLASS = 'hedwig.validators.protobuf.ProtobufValidator'

        try:
            from tests.protobuf_factory import ProtobufMessageFactory  # noqa

            def _encode_proto(msg):
                return msg.SerializeToString(deterministic=True)

            # make maps deterministically ordered
            with mock.patch("hedwig.validators.protobuf.ProtobufValidator._encode_proto", side_effect=_encode_proto):
                yield ProtobufMessageFactory
        except ImportError:
            pytest.skip("Protobuf factory not importable")


@pytest.fixture()
def message_data(message_factory):
    return message_factory.build(msg_type=MessageType.trip_created)


@pytest.fixture()
def message(message_factory):
    return message_factory(msg_type=MessageType.trip_created)


@pytest.fixture()
def message_with_trace(message_factory):
    return message_factory(
        msg_type=MessageType.trip_created,
        metadata__headers__traceparent="00-aa2ada259e917551e16da4a0ad33db24-662fd261d30ec74c-01",
    )


@contextmanager
def _mock_boto3():
    settings.AWS_REGION = 'us-west-1'

    with mock_aws(), mock.patch("hedwig.backends.aws.boto3", autospec=True) as boto3_mock:
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
    with mock.patch.object(MockHedwigPublisherBackend, '_publish'):
        yield MockHedwigPublisherBackend()


@pytest.fixture(params=[True, False], ids=["message-attrs", "no-message-attrs"])
def use_transport_message_attrs(request, settings):
    settings.HEDWIG_USE_TRANSPORT_MESSAGE_ATTRIBUTES = request.param
    yield settings.HEDWIG_USE_TRANSPORT_MESSAGE_ATTRIBUTES
