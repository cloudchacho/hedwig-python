import pprint
from distutils.version import StrictVersion
from unittest import mock

import pytest


__all__ = ['mock_hedwig_publish']


@pytest.fixture()
def mock_hedwig_publish():
    from hedwig.publisher import publish

    with mock.patch('hedwig.publisher.publish', wraps=publish) as mock_publish, mock.patch(
        'hedwig.publisher._publish_over_sns'
    ):

        def assert_message_published(msg_type, data=None, version=StrictVersion('1.0')):
            """
            Helper function to check if a Hedwig message with given type, data
            and schema version was sent.
            """
            if not isinstance(version, StrictVersion):
                version = StrictVersion(version)

            assert any(
                msg.type == msg_type and (data is None or msg.data) == data and msg.data_schema_version == version
                for (msg,), _ in mock_publish.call_args_list
            ), pprint.pformat(
                [(msg.type, msg.data, msg.data_schema_version) for (msg,), _ in mock_publish.call_args_list]
            )

        def assert_message_not_published(msg_type):
            """
            Helper function to check that a Hedwig message of given type was NOT sent.
            """
            assert all(msg.type != msg_type for (msg,), _ in mock_publish.call_args_list), pprint.pformat(
                [(msg.type, msg.data, msg.data_schema_version) for (msg,), _ in mock_publish.call_args_list]
            )

        mock_publish.assert_message_published = assert_message_published
        mock_publish.assert_message_not_published = assert_message_not_published
        yield mock_publish
