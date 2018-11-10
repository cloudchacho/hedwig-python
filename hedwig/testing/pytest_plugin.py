import pprint
from distutils.version import StrictVersion
from typing import Optional, Union, Generator
from unittest import mock

import pytest


__all__ = ['mock_hedwig_publish']


class HedwigPublishMock(mock.MagicMock):
    """
    Custom mock class used by :meth:`hedwig.testing.pytest_plugin.mock_hedwig_publish` to mock the publisher.
    """

    def _message_published(self, msg_type, data: Optional[dict], version: Union[str, StrictVersion]) -> bool:
        return any(
            msg.type == msg_type and (data is None or msg.data) == data and msg.data_schema_version == version
            for (msg,), _ in self.call_args_list
        )

    def _error_message(self) -> str:
        return pprint.pformat([(msg.type, msg.data, msg.data_schema_version) for (msg,), _ in self.call_args_list])

    def assert_message_published(
        self, msg_type, data: Optional[dict] = None, version: Union[str, StrictVersion] = StrictVersion('1.0')
    ) -> None:
        """
        Helper function to check if a Hedwig message with given type, data
        and schema version was sent.
        """
        if not isinstance(version, StrictVersion):
            version = StrictVersion(version)

        assert self._message_published(msg_type, data, version), self._error_message()

    def assert_message_not_published(
        self, msg_type, data: Optional[dict] = None, version: Union[str, StrictVersion] = StrictVersion('1.0')
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
    from hedwig.publisher import publish

    with mock.patch(
        'hedwig.publisher.publish', wraps=publish, new_callable=HedwigPublishMock
    ) as mock_publish, mock.patch('hedwig.publisher._publish_over_sns'):
        yield mock_publish
