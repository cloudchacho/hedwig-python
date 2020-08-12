import json
import math
from decimal import Decimal
import uuid

from jsonschema import SchemaError
import pytest

from hedwig.exceptions import ValidationError
from hedwig.validators.jsonschema import JSONSchemaValidator
from hedwig.testing.factories import MessageFactory

from tests.models import MessageType


class TestJSONDefault:
    @pytest.mark.parametrize('value', [1469056316326, 1469056316326.123])
    def test__convert_to_json_decimal(self, value):
        message = MessageFactory(msg_type=MessageType.trip_created, data__decimal=Decimal(value))
        assert json.loads(message.serialize())['data']['decimal'] == float(message.data['decimal'])

    @pytest.mark.parametrize('value', [math.nan, math.inf, -math.inf])
    def test__convert_to_json_disallow_nan(self, value, message_data):
        message = MessageFactory(msg_type=MessageType.trip_created, data__nan=value)
        with pytest.raises(ValueError):
            message.serialize()

    def test__convert_to_json_non_serializable(self, message_data):
        message = MessageFactory(msg_type=MessageType.trip_created, data__obj=object())
        with pytest.raises(TypeError):
            message.serialize()


class TestJSONSchemaValidator:
    def setup_method(self, method):
        self.validator = JSONSchemaValidator()

    def test_constructor_checks_schema(self):
        schema = {}
        with pytest.raises(SchemaError):
            JSONSchemaValidator(schema)

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
    def test_check_schema(self, schema: dict, schema_exc_error):
        with pytest.raises(SchemaError) as exc_context:
            JSONSchemaValidator(schema)

        assert schema_exc_error in exc_context.value.args[0]

    def test_serialize(self):
        message = MessageFactory(msg_type=MessageType.trip_created, model_version=1)
        payload = {
            'format_version': '1.0',
            'schema': 'https://hedwig.automatic.com/schema#/schemas/trip_created/1.0',
            'id': message.id,
            'metadata': {'timestamp': message.timestamp, 'publisher': message.publisher, 'headers': message.headers},
            'data': message.data,
        }
        assert payload == json.loads(self.validator.serialize(message))

    def test_deserialize_raises_error_invalid_schema(self):
        payload = '''{}'''
        with pytest.raises(ValidationError) as e:
            self.validator.deserialize(payload, None)
        assert '"\'id\' is a required property"' in str(e.value.args[0])

        payload = '''{
            "format_version": "1.0",
            "schema": "https://wrong.host/schema#/schemas/trip_created",
            "id": "2acd99ec-47ac-3232-a7f3-6049146aad15",
            "metadata": {},
            "data": {}
        }'''
        with pytest.raises(ValidationError) as e:
            self.validator.deserialize(payload, None)
        assert e.value.args[0] == 'Invalid schema found: https://wrong.host/schema#/schemas/trip_created'

        payload = '''{
            "format_version": "1.0",
            "schema": "https://wrong.host/schema#/schemas/trip_created/1.0",
            "id": "2acd99ec-47ac-3232-a7f3-6049146aad15",
            "metadata": {},
            "data": {}
        }'''
        with pytest.raises(ValidationError) as e:
            self.validator.deserialize(payload, None)
        assert e.value.args[0] == 'message schema must start with "https://hedwig.automatic.com/schema"'

        payload = '''{
            "format_version": "1.0",
            "schema": "https://hedwig.automatic.com/schema#/schemas/trip_created/9.0",
            "id": "2acd99ec-47ac-3232-a7f3-6049146aad15",
            "metadata": {},
            "data": {}
        }'''
        with pytest.raises(ValidationError) as e:
            self.validator.deserialize(payload, None)
        assert e.value.args[0] == 'definition not found in schema'

    def test_deserialize_fails_on_invalid_json(self, message_data):
        with pytest.raises(ValidationError):
            self.validator.deserialize("bad json", None)

    def test_deserialize_raises_error_invalid_data(self):
        payload = '''{
            "format_version": "1.0",
            "schema": "https://hedwig.automatic.com/schema#/schemas/trip_created/1.0",
            "id": "2acd99ec-47ac-3232-a7f3-6049146aad15",
            "metadata": {},
            "data": {}
        }'''
        with pytest.raises(ValidationError):
            self.validator.deserialize(payload, None)

    def test_serialize_raises_error_invalid_schema(self):
        message = MessageFactory(msg_type='foobar')
        with pytest.raises(ValidationError) as e:
            self.validator.serialize(message)
        assert e.value.args[0] == 'definition not found in schema'

    def test_serialize_raises_error_invalid_version(self):
        message = MessageFactory(msg_type=MessageType.trip_created, model_version=9)
        with pytest.raises(ValidationError) as e:
            self.validator.serialize(message)
        assert e.value.args[0] == 'definition not found in schema'

    def test_serialize_raises_error_invalid_data(self):
        message = MessageFactory(data={})
        with pytest.raises(ValidationError):
            self.validator.serialize(message)

    def test_check_human_uuid(self):
        assert self.validator._check_human_uuid(str(uuid.uuid4()))
        assert self.validator._check_human_uuid('6cac5588-24cc-4b4f-bbf9-7dc0ce93f96e')
        assert self.validator._check_human_uuid('793befdf-56c2-416a-92ed-420e62b33eb5')

    def test_check_human_uuid_fails(self):
        assert not self.validator._check_human_uuid(uuid.uuid4().hex)
        assert not self.validator._check_human_uuid('6cac5588')
        assert not self.validator._check_human_uuid('yyyyyyyy-tttt-416a-92ed-420e62b33eb5')
        assert not self.validator._check_human_uuid(uuid.uuid4())


def test_custom_validator(settings):
    settings.HEDWIG_DATA_VALIDATOR_CLASS = 'tests.validator.CustomValidator'

    with pytest.raises(ValidationError):
        MessageFactory(msg_type=MessageType.trip_created, addition_version=1, data__vin='o' * 17).serialize()
