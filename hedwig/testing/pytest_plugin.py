import pprint
from contextlib import ExitStack
from distutils.version import StrictVersion
from enum import Enum
from typing import Optional, Union, Generator, Any
from unittest import mock

import pytest


__all__ = ['mock_hedwig_publish']


class HedwigPublishMock(mock.MagicMock):
    """
    Custom mock class used by :meth:`hedwig.testing.pytest_plugin.mock_hedwig_publish` to mock the publisher.
    """

    def _message_published(
        self, msg_type: Union[str, Enum], data: Optional[Any], version: Union[str, StrictVersion]
    ) -> bool:
        if isinstance(msg_type, Enum):
            msg_type = msg_type.value
        return any(
            msg.type == msg_type and (data is None or msg.data == data) and msg.version == version
            for (msg,), _ in self.call_args_list
        )

    def _error_message(self) -> str:
        return pprint.pformat([(msg.type, msg.data, msg.version) for (msg,), _ in self.call_args_list])

    def assert_message_published(
        self, msg_type: Union[str, Enum], data: Any = None, version: Union[str, StrictVersion] = StrictVersion('1.0')
    ) -> None:
        """
        Helper function to check if a Hedwig message with given type, data
        and schema version was sent.
        """
        if not isinstance(version, StrictVersion):
            version = StrictVersion(version)

        assert self._message_published(msg_type, data, version), self._error_message()

    def assert_message_not_published(
        self, msg_type: Union[str, Enum], data: Any = None, version: Union[str, StrictVersion] = StrictVersion('1.0')
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

    with ExitStack() as s:
        try:
            import hedwig.backends.aws  # noqa

            s.enter_context(mock.patch("hedwig.backends.aws.boto3", autospec=True))
        except ImportError:
            pass

        try:
            import hedwig.backends.gcp  # noqa

            s.enter_context(mock.patch("hedwig.backends.gcp.pubsub_v1", autospec=True))
            s.enter_context(
                mock.patch("hedwig.backends.gcp.google_auth_default", autospec=True, return_value=(None, "DUMMY"))
            )
        except ImportError:
            pass

        publisher_backend = get_publisher_backend()

        with mock.patch(
            'hedwig.backends.base.HedwigPublisherBaseBackend.publish',
            wraps=publisher_backend.publish,
            new_callable=HedwigPublishMock,
        ) as mock_publish, mock.patch.object(publisher_backend, '_publish'):
            yield mock_publish
