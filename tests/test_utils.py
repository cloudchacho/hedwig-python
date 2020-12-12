import logging
from unittest import mock
from uuid import uuid4

import pytest

import hedwig.utils


@pytest.fixture(name="logger_mock", params=["structlog", "stdlog"])
def _logger_mock(request):
    if request.param == "stdlog":
        with mock.patch.object(hedwig.utils, "structlog", None), mock.patch("hedwig.utils.logging") as m:
            yield request.param, m
    elif request.param == "structlog":
        with mock.patch("hedwig.utils.structlog") as m:
            yield request.param, m


def test_log(logger_mock):
    mock_logger = logger_mock[1]
    logger = logger_mock[0]
    message = "foobar"
    hedwig.utils.log(__name__, logging.INFO, message)
    if logger == "stdlog":
        mock_logger.getLogger(__name__).log.assert_called_once_with(logging.INFO, message)
    elif logger == "structlog":
        mock_logger.getLogger(__name__).info.assert_called_once_with(message)


def test_log_exception(logger_mock):
    mock_logger = logger_mock[1]
    logger = logger_mock[0]
    message = "foobar"
    hedwig.utils.log(__name__, logging.ERROR, message, exc_info=True)
    if logger == "stdlog":
        mock_logger.getLogger(__name__).log.assert_called_once_with(logging.ERROR, message, exc_info=True)
    elif logger == "structlog":
        mock_logger.getLogger(__name__).error.assert_called_once_with(message, exc_info=True)


def test_log_extra(logger_mock):
    mock_logger = logger_mock[1]
    logger = logger_mock[0]
    message = "foobar"
    u = uuid4()
    hedwig.utils.log(__name__, logging.ERROR, message, extra={"uuid": str(u), "another": "field", "yet_another": 1})
    if logger == "stdlog":
        mock_logger.getLogger(__name__).log.assert_called_once_with(
            logging.ERROR, message, extra={"uuid": str(u), "another": "field", "yet_another": 1}
        )
    elif logger == "structlog":
        mock_logger.getLogger(__name__).error.assert_called_once_with(
            message, uuid=str(u), another="field", yet_another=1
        )
