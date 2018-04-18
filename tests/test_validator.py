import uuid

import pytest

from hedwig.exceptions import ValidationError
from hedwig.models import MessageType
from hedwig.validator import MessageValidator
from hedwig.testing.factories import MessageFactory


class TestMessageValidator:
    def setup_method(self, method):
        self.validator = MessageValidator()

    def test_validate(self):
        message = MessageFactory(msg_type=MessageType.trip_created, model_version=1, validate=False)
        self.validator.validate(message)

    def test_validate_raises_error_invalid_schema(self):
        message = MessageFactory(schema='mickey-mouse', validate=False)
        with pytest.raises(ValidationError):
            self.validator.validate(message)

        message = MessageFactory(schema='https://hedwig.automatic.com/schema#/schemas/mickey-mouse/1.0', validate=False)
        with pytest.raises(ValidationError):
            self.validator.validate(message)

    def test_validate_raises_errors(self):
        message = MessageFactory(data={}, validate=False)
        with pytest.raises(ValidationError):
            self.validator.validate(message)

    def test_check_human_uuid(self):
        assert self.validator.check_human_uuid(str(uuid.uuid4()))
        assert self.validator.check_human_uuid('6cac5588-24cc-4b4f-bbf9-7dc0ce93f96e')
        assert self.validator.check_human_uuid('793befdf-56c2-416a-92ed-420e62b33eb5')

    def test_check_human_uuid_fails(self):
        assert not self.validator.check_human_uuid(uuid.uuid4().hex)
        assert not self.validator.check_human_uuid('6cac5588')
        assert not self.validator.check_human_uuid('yyyyyyyy-tttt-416a-92ed-420e62b33eb5')


def test_custom_validator(settings):
    settings.HEDWIG_DATA_VALIDATOR_CLASS = 'tests.validator.CustomValidator'

    message = MessageFactory(msg_type=MessageType.trip_created, addition_version=1, data__vin='o' * 17, validate=False)
    with pytest.raises(ValidationError):
        message.validate()
