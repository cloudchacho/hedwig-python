import pytest

import hedwig.conf


def test_fail_import_bad_value(settings):
    settings.HEDWIG_DEFAULT_HEADERS = 'foo'

    with pytest.raises(ImportError):
        hedwig.conf.settings.HEDWIG_DEFAULT_HEADERS


def test_fail_import_bad_module(settings):
    settings.HEDWIG_DEFAULT_HEADERS = 'foo.bar'

    with pytest.raises(ImportError):
        hedwig.conf.settings.HEDWIG_DEFAULT_HEADERS


def test_fail_import_bad_attr(settings):
    settings.HEDWIG_DEFAULT_HEADERS = 'tests.validator.foobar'

    with pytest.raises(ImportError):
        hedwig.conf.settings.HEDWIG_DEFAULT_HEADERS
