from typing import List, Type

import pytest

from hedwig.exceptions import ValidationError

pytest.importorskip('google.protobuf')

from google.protobuf import json_format  # noqa
from google.protobuf.message import Message as ProtoMessage  # noqa
from hedwig.testing.factories.protobuf import ProtobufMessageFactory  # noqa
from hedwig.validators.protobuf import ProtobufJSONValidator, SchemaError  # noqa
from hedwig.protobuf.container_pb2 import PayloadV1  # noqa
from tests.models import MessageType  # noqa
from tests.schemas.protos import protobuf_pb2, protobuf_bad_pb2  # noqa
from tests import test_validators  # noqa


class TestProtobufJSONValidator:
    def _validator(self):
        return ProtobufJSONValidator()

    @pytest.mark.parametrize(
        'proto_messages,schema_exc_error',
        [
            [
                [
                    protobuf_bad_pb2.DeviceCreated,
                    protobuf_pb2.TripCreatedV1,
                    protobuf_pb2.TripCreatedV2,
                    protobuf_pb2.DeviceCreatedV1,
                    protobuf_pb2.VehicleCreatedV1,
                ],
                "Couldn't determine message type for Protobuf message class '<class 'protobuf_bad_pb2.DeviceCreated'>'",
            ],
            [
                [
                    protobuf_pb2.TripCreatedV1,
                    protobuf_pb2.DeviceCreatedV1,
                    protobuf_pb2.VehicleCreatedV1,
                ],
                "Invalid message_type, major version: 'trip_created/2', not found in declared messages",
            ],
            [
                [
                    protobuf_bad_pb2.TripCreatedV3,
                    protobuf_pb2.TripCreatedV1,
                    protobuf_pb2.TripCreatedV2,
                    protobuf_pb2.DeviceCreatedV1,
                    protobuf_pb2.VehicleCreatedV1,
                ],
                "Protobuf message class '<class 'protobuf_bad_pb2.TripCreatedV3'>' mismatch in major version: '3' !="
                " '2'",
            ],
            [
                [
                    protobuf_bad_pb2.TripCreated,
                    protobuf_pb2.TripCreatedV1,
                    protobuf_pb2.TripCreatedV2,
                    protobuf_pb2.DeviceCreatedV1,
                    protobuf_pb2.VehicleCreatedV1,
                ],
                "Duplicate Protobuf message declared for 'trip_created/1'",
            ],
        ],
    )
    def test_check_schema(self, proto_messages: List[Type[ProtoMessage]], schema_exc_error):
        with pytest.raises(SchemaError) as exc_context:
            ProtobufJSONValidator(proto_messages)

        assert schema_exc_error in exc_context.value.args[0]

    def test_serialize(self, use_transport_message_attrs):
        message = ProtobufMessageFactory(
            msg_type=MessageType.trip_created, model_version=1, protobuf_schema_module=protobuf_pb2
        )
        if not use_transport_message_attrs:
            msg = PayloadV1()
            msg.format_version = '1.0'
            msg.schema = 'trip_created/1.0'
            msg.id = message.id
            msg.metadata.timestamp.FromMilliseconds(message.timestamp)
            msg.metadata.publisher = message.publisher
            for k, v in message.headers.items():
                msg.metadata.headers[k] = v
            msg.data.Pack(message.data)
            attributes = message.headers
            serialized = self._validator().serialize(message)
            serialized_msg = PayloadV1()
            json_format.Parse(serialized[0], serialized_msg)
            assert msg == serialized_msg
            assert attributes == serialized[1]
        else:
            msg = message.data
            attributes = {
                "hedwig_format_version": '1.0',
                "hedwig_schema": "trip_created/1.0",
                "hedwig_id": message.id,
                "hedwig_publisher": message.publisher,
                "hedwig_message_timestamp": str(message.timestamp),
                **message.headers,
            }
            serialized = self._validator().serialize(message)
            serialized_msg = protobuf_pb2.TripCreatedV1()
            json_format.Parse(serialized[0], serialized_msg)
            assert attributes == serialized[1]
            assert msg == serialized_msg

    def test_deserialize_raises_error_invalid_schema(self):
        validator = self._validator()

        payload = '{}'
        with pytest.raises(ValidationError) as e:
            validator.deserialize(payload, {}, None)
        assert 'Invalid message attribute: hedwig_format_version must be string, found: None' in str(e.value.args[0])

        payload = '{}'
        attrs = {
            "hedwig_format_version": "1.0",
            "hedwig_schema": "trip_created",
            "hedwig_id": "2acd99ec-47ac-3232-a7f3-6049146aad15",
            "hedwig_publisher": "",
            "hedwig_headers": "{}",
            "hedwig_message_timestamp": "1",
        }
        with pytest.raises(ValidationError) as e:
            validator.deserialize(payload, attrs, None)
        assert e.value.args[0] == 'Invalid schema found: trip_created'

        payload = '{}'
        attrs = {
            "hedwig_format_version": "1.0",
            "hedwig_schema": "trip_created/9.0",
            "hedwig_id": "2acd99ec-47ac-3232-a7f3-6049146aad15",
            "hedwig_publisher": "",
            "hedwig_headers": "{}",
            "hedwig_message_timestamp": "1",
        }
        with pytest.raises(ValidationError) as e:
            validator.deserialize(payload, attrs, None)
        assert e.value.args[0] == "Protobuf message class not found for 'trip_created/9'"

    def test_deserialize_raises_error_invalid_schema_container(self, settings):
        settings.HEDWIG_USE_TRANSPORT_MESSAGE_ATTRIBUTES = False

        validator = self._validator()

        payload = '{}'
        with pytest.raises(ValidationError) as e:
            validator.deserialize(payload, {}, None)
        assert '' in str(e.value.args[0])

        msg = PayloadV1()
        msg.format_version = '1.0'
        msg.schema = 'trip_created'
        msg.id = "2acd99ec-47ac-3232-a7f3-6049146aad15"
        msg.metadata.timestamp.FromMilliseconds(1)
        msg.metadata.publisher = ""
        payload = json_format.MessageToJson(msg)

        with pytest.raises(ValidationError) as e:
            validator.deserialize(payload, {}, None)
        assert e.value.args[0] == 'Invalid schema found: trip_created'

        msg.schema = 'trip_created/9.0'
        payload = json_format.MessageToJson(msg)

        with pytest.raises(ValidationError) as e:
            validator.deserialize(payload, {}, None)
        assert e.value.args[0] == "Protobuf message class not found for 'trip_created/9'"

    def test_deserialize_fails_on_invalid_payload(self):
        with pytest.raises(ValidationError):
            self._validator().deserialize(b"bad proto", {}, None)

    def test_deserialize_raises_error_invalid_data(self):
        payload = 'not-json'
        attrs = {
            "hedwig_format_version": "1.0",
            "hedwig_schema": "trip_created/1.0",
            "hedwig_id": "2acd99ec-47ac-3232-a7f3-6049146aad15",
            "hedwig_publisher": "",
            "hedwig_headers": "{}",
            "hedwig_message_timestamp": "1",
        }
        with pytest.raises(ValidationError) as e:
            self._validator().deserialize(payload, attrs, None)
        assert e.value.args[0] in [
            'Invalid data for message: TripCreatedV1: Failed to load JSON: Expecting value: line 1 column 1 (char 0).',
        ]

    def test_serialize_no_error_invalid_data(self):
        message = ProtobufMessageFactory(
            msg_type='device.created',
            data=protobuf_bad_pb2.DeviceCreated(foobar=1),
            protobuf_schema_module=protobuf_pb2,
        )
        # invalid data is ignored so long as its a valid protobuf class
        self._validator().serialize(message)

    def test_serialize_raises_error_invalid_minor_version(self):
        message = ProtobufMessageFactory(
            msg_type='device.created',
            addition_version=1,
            data=protobuf_pb2.DeviceCreatedV1(device_id="abcd", user_id="U_123"),
            protobuf_schema_module=protobuf_pb2,
        )
        with pytest.raises(ValidationError) as e:
            self._validator().serialize(message)
        assert e.value.args[0] == 'Unknown minor version: 1, last known minor version: 0'

    def test_serialize_raises_error_invalid_headers(self):
        message = ProtobufMessageFactory(
            msg_type='device.created',
            protobuf_schema_module=protobuf_pb2,
            metadata__headers__hedwig_foo="bar",
        )
        with pytest.raises(ValidationError) as e:
            self._validator().serialize(message)
        assert e.value.args[0] == "Invalid header key: 'hedwig_foo' - can't begin with reserved namespace 'hedwig_'"
