import pprint
from distutils.version import StrictVersion
from typing import Optional, Union, Generator
from unittest import mock

import pytest


__all__ = ['mock_hedwig_publish']


class AnyDict(dict):
    """An object equal to any dict."""

    def __eq__(self, other):
        return isinstance(other, dict)

    def __repr__(self):
        return f'{type(self).__name__}()'


class HedwigPublishMock(mock.MagicMock):
    """
    Custom mock class used by :meth:`hedwig.testing.pytest_plugin.mock_hedwig_publish` to mock the publisher.
    """

    def _message_published(self, msg_type, data: Optional[dict], version: Union[str, StrictVersion]) -> bool:
        return any(
            msg.type == msg_type and msg.data == data and msg.data_schema_version == version
            for (msg,), _ in self.call_args_list
        )

    def _error_message(self) -> str:
        return pprint.pformat([(msg.type, msg.data, msg.data_schema_version) for (msg,), _ in self.call_args_list])

    def assert_message_published(
        self, msg_type, data: Optional[dict] = AnyDict(), version: Union[str, StrictVersion] = StrictVersion('1.0')
    ) -> None:
        """
        Helper function to check if a Hedwig message with given type, data
        and schema version was sent.
        """
        if not isinstance(version, StrictVersion):
            version = StrictVersion(version)

        assert self._message_published(msg_type, data, version), self._error_message()

    def assert_message_not_published(
        self, msg_type, data: Optional[dict] = AnyDict(), version: Union[str, StrictVersion] = StrictVersion('1.0')
    ) -> None:
        """
        Helper function to check that a Hedwig message of given type, data
        and schema was NOT sent.
        """
        if not isinstance(version, StrictVersion):
            version = StrictVersion(version)

        assert not self._message_published(msg_type, data, version), self._error_message()


@pytest.fixture()
def mock_hedwig_publish() -> Generator[HedwigPublishMock, None, None]:
    """
    A pytest fixture that mocks Hedwig publisher and lets you verify that your test publishes appropriate messages.
    """
    from hedwig.backends.utils import get_publisher_backend

    with mock.patch("hedwig.backends.aws.boto3", autospec=True), mock.patch(
        "hedwig.backends.gcp.pubsub_v1", autospec=True
    ):
        publisher_backend = get_publisher_backend()

        with mock.patch(
            'hedwig.backends.base.HedwigPublisherBaseBackend.publish',
            wraps=publisher_backend.publish,
            new_callable=HedwigPublishMock,
        ) as mock_publish, mock.patch.object(publisher_backend, '_publish'):
            yield mock_publish
