from unittest import mock
import uuid

import pytest

from hedwig.callback import Callback
from hedwig.exceptions import ConfigurationError, CallbackNotFound
from hedwig.models import Message, MessageType
from tests.handlers import trip_created_handler


def default_headers() -> dict:
    return {'request_id': str(uuid.uuid4())}


class TestCallback:
    @staticmethod
    def f(message):
        pass

    @staticmethod
    def f_kwargs(**kwargs):
        pass

    @staticmethod
    def f_args(message, *args, **kwargs):
        pass

    @staticmethod
    def f_invalid_annotation(message: dict):
        pass

    @staticmethod
    def f_no_param():
        pass

    @staticmethod
    def f_unknown_param(message, unknown):
        pass

    def test_constructor(self):
        task_obj = Callback(TestCallback.f)
        assert task_obj.fn is TestCallback.f

    def test_constructor_disallow_kwargs(self):
        with pytest.raises(ConfigurationError):
            Callback(TestCallback.f_kwargs)

    def test_constructor_disallow_args(self):
        with pytest.raises(ConfigurationError):
            Callback(TestCallback.f_args)

    def test_constructor_bad_annotation(self):
        with pytest.raises(ConfigurationError):
            Callback(TestCallback.f_invalid_annotation)

    def test_constructor_no_param(self):
        with pytest.raises(ConfigurationError):
            Callback(TestCallback.f_no_param)

    def test_constructor_unknown_param(self):
        with pytest.raises(ConfigurationError):
            Callback(TestCallback.f_unknown_param)

    def test_call(self, message):
        _f = mock.MagicMock()

        def f(message: Message):
            _f(message)

        Callback(f).call(message)
        _f.assert_called_once_with(message)

    def test_find_by_message(self):
        assert Callback.find_by_message(MessageType.trip_created, 1)._fn == trip_created_handler

    def test_find_by_name_fail(self):
        with pytest.raises(CallbackNotFound):
            Callback.find_by_message(MessageType.vehicle_created, 1)

    def test_str(self):
        assert str(Callback(self.f)) == 'Hedwig task: f'
