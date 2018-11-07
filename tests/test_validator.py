from unittest import mock
import uuid

from jsonschema import SchemaError
import pytest

from hedwig.exceptions import ValidationError
from hedwig.models import MessageType
from hedwig.validator import MessageValidator
from hedwig.testing.factories import MessageFactory


class TestMessageValidator:
    def setup_method(self, method):
        self.validator = MessageValidator()

    @mock.patch('hedwig.validator.MessageValidator.check_schema')
    def test_constructor_checks_schema(self, mock_check_schema):
        schema = {'schemas': []}
        MessageValidator(schema)
        mock_check_schema.assert_called_once_with(schema)

    @pytest.mark.parametrize(
        'schema,schema_exc_error',
        [
            [{'schemas': []}, "Invalid schema file: expected key 'schemas' with non-empty value"],
            [
                {'schemas': {"device.created": []}},
                "Invalid definition for message type: 'device.created', value must contain a dict of valid versions",
            ],
            [
                {'schemas': {"device.created": {'fail-pattern': []}}},
                "Invalid version 'fail-pattern' for message type: 'device.created'",
            ],
            [{'schemas': {"device.created": {'1.*': []}}}, "Invalid version '1.*' for message type: 'device.created'"],
            [
                {
                    'schemas': {
                        "device.created": {'1.*': {}},
                        "vehicle_created": {'1.*': {}},
                        "trip_created": {'1.*': {}},
                    }
                },
                "Schema not found for 'trip_created' v2.*",
            ],
        ],
    )
    def test_check_schema(self, schema, schema_exc_error):
        with pytest.raises(SchemaError) as exc_context:
            MessageValidator(schema)

        assert schema_exc_error in exc_context.value.args[0]

    def test_validate(self):
        message = MessageFactory(msg_type=MessageType.trip_created, model_version=1)
        self.validator.validate(message)

    def test_validate_raises_error_invalid_schema(self):
        with pytest.raises(ValidationError) as e:
            MessageFactory(schema='https://wrong.host/schema#/schemas/trip_created/1.0')
        assert e.value.args[0] == 'message schema must start with "https://hedwig.automatic.com/schema"'

        with pytest.raises(ValidationError) as e:
            MessageFactory(schema='https://hedwig.automatic.com/schema#/schemas/trip_created/9.0')
        assert e.value.args[0] == 'definition not found in schema'

    def test_validate_raises_errors(self):
        with pytest.raises(ValidationError):
            MessageFactory(data={})

    def test_check_human_uuid(self):
        assert self.validator.check_human_uuid(str(uuid.uuid4()))
        assert self.validator.check_human_uuid('6cac5588-24cc-4b4f-bbf9-7dc0ce93f96e')
        assert self.validator.check_human_uuid('793befdf-56c2-416a-92ed-420e62b33eb5')

    def test_check_human_uuid_fails(self):
        assert not self.validator.check_human_uuid(uuid.uuid4().hex)
        assert not self.validator.check_human_uuid('6cac5588')
        assert not self.validator.check_human_uuid('yyyyyyyy-tttt-416a-92ed-420e62b33eb5')
        assert not self.validator.check_human_uuid(uuid.uuid4())


def test_custom_validator(settings):
    settings.HEDWIG_DATA_VALIDATOR_CLASS = 'tests.validator.CustomValidator'

    with pytest.raises(ValidationError):
        MessageFactory(msg_type=MessageType.trip_created, addition_version=1, data__vin='o' * 17)
