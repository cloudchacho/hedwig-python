import threading
from typing import Any
from unittest import mock


def mock_return_once(m: mock.Mock, first_result: Any, rest: Any, event: threading.Event):
    """
    Sets up mock callable such that it returns a result first the time, and a different result all other times it's
    called.
    Useful for functions that may be called indefinitely in a while loop
    :param m: the mock object
    :param first_result: value to return 1st time the mock is called
    :param rest: value to return after 1st time the mock is called
    :param event: Set an event after mock is called the 1st time.
    :return:
    """

    def f(*args, **kwargs):
        if f.called:
            return rest

        f.called = True
        event.set()
        return first_result

    f.called = False

    m.side_effect = f
