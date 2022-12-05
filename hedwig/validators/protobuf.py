import base64
import re
import typing
from copy import deepcopy
from distutils.version import StrictVersion
from typing import Tuple, Union, TypeVar, Type, List, Optional, MutableMapping, cast

import funcy
from google.protobuf import json_format
from google.protobuf.any_pb2 import Any
from google.protobuf.message import DecodeError, Message as ProtoMessage
from google.protobuf.struct_pb2 import Value

from hedwig.conf import settings
from hedwig.exceptions import ValidationError
from hedwig.protobuf import options_pb2
from hedwig.protobuf.container_pb2 import PayloadV1
from hedwig.protobuf.options_pb2 import MessageOptions
from hedwig.validators.base import HedwigBaseValidator, MetaAttributes


class SchemaError(Exception):
    pass


ProtoMessageT = TypeVar("ProtoMessageT", bound=ProtoMessage)


def decode_proto_json(msg_class: typing.Any, value: Union[str, bytes]) -> ProtoMessageT:  # type: ignore
    assert isinstance(value, str)

    msg: ProtoMessageT = msg_class()
    json_format.Parse(value, msg, ignore_unknown_fields=True)
    return msg


def encode_proto_json(msg: ProtoMessage) -> str:
    return json_format.MessageToJson(msg, preserving_proto_field_name=True, indent=0).replace("\n", "")


class ProtobufValidator(HedwigBaseValidator):
    """
    A validator that encodes the payload using Protobuf binary format.
    """

    proto_messages: MutableMapping[Tuple[str, int], Type[ProtoMessage]]
    """
    The list of protoc compiled python classes - supplied by app
    """

    _version_pattern_re = re.compile(r"^([0-9]+)\.\*$")

    _message_name_re = re.compile(r"^(.*)V(\d+)$")

    def __init__(self, proto_messages: Optional[List[Type[ProtoMessage]]] = None) -> None:
        # schema encoding, eg: hedwig.automatic.com/schema#/schemas/trip.created/1.0
        schema_fmt = '{message_type}/{message_version}'
        schema_re = re.compile(r'([^/]+)/([^/]+)$')
        self.proto_messages = {}

        super().__init__(schema_fmt, schema_re, StrictVersion('1.0'))

        if proto_messages is None:
            proto_messages = settings.HEDWIG_PROTOBUF_MESSAGES

        self._check_schema(proto_messages)

    def _decode_proto(self, msg_class: typing.Any, value: Union[str, bytes]) -> ProtoMessageT:  # type: ignore
        """
        Decode an arbitrary protobuf message from value
        """
        assert isinstance(value, bytes)

        msg: ProtoMessageT = msg_class()
        msg.ParseFromString(value)
        return msg

    def _encode_proto(self, msg: ProtoMessage) -> Union[str, bytes]:
        """
        Encode an arbitrary protobuf message into value
        """
        return msg.SerializeToString()

    def _verify_known_minor_version(self, message_type: str, full_version: StrictVersion):
        msg_class = self.proto_messages.get((message_type, full_version.version[0]))
        if not msg_class:
            raise ValidationError(f"Protobuf message class not found for '{message_type}/{full_version.version[0]}'")

        options: MessageOptions = msg_class.DESCRIPTOR.GetOptions().Extensions[options_pb2.message_options]
        if options.minor_version < full_version.version[1]:
            raise ValidationError(
                f'Unknown minor version: {full_version.version[1]}, last known minor version: '
                f'{options.minor_version}'
            )

    def _extract_data(
        self, message_payload: Union[bytes, str], attributes: dict, use_transport_attributes: bool
    ) -> Tuple[MetaAttributes, bytes]:
        assert isinstance(message_payload, (bytes, str))

        if not use_transport_attributes:
            try:
                msg_payload = self._decode_proto(PayloadV1, message_payload)  # type: ignore
            except (DecodeError, RuntimeError, AssertionError, json_format.ParseError) as e:
                raise ValidationError(f"Invalid data for message: PayloadV1: {e}")

            data = msg_payload.data
            meta_attrs = MetaAttributes(
                msg_payload.metadata.timestamp.ToMilliseconds(),
                msg_payload.metadata.publisher,
                dict(msg_payload.metadata.headers),
                msg_payload.id,
                msg_payload.schema,
                msg_payload.format_version,
            )
        else:
            data = message_payload
            meta_attrs = self._decode_meta_attributes(attributes)
            if meta_attrs.format_version != self._current_format_version:
                raise ValidationError(f"Invalid format version: {meta_attrs.format_version}")
        return meta_attrs, data

    def _extract_data_firehose(self, line: str) -> Tuple[MetaAttributes, bytes]:
        assert isinstance(line, str)

        try:
            msg_payload = decode_proto_json(PayloadV1, line)  # type: ignore
        except (DecodeError, RuntimeError, AssertionError, json_format.ParseError) as e:
            raise ValidationError(f"Invalid data for message: PayloadV1: {e}")

        data = msg_payload.data
        if data.Is(Value.DESCRIPTOR):
            # unknown data types are encoded as `encode(PayloadV1(data=Value(string_value=base64(binary))))`
            value_msg = Value()
            data.Unpack(value_msg)
            assert value_msg.WhichOneof("kind") == "string_value"
            data = base64.decodebytes(value_msg.string_value.encode("utf8"))

        meta_attrs = MetaAttributes(
            msg_payload.metadata.timestamp.ToMilliseconds(),
            msg_payload.metadata.publisher,
            dict(msg_payload.metadata.headers),
            msg_payload.id,
            msg_payload.schema,
            msg_payload.format_version,
        )
        return meta_attrs, data

    def _decode_data(
        self,
        meta_attrs: MetaAttributes,
        message_type: str,
        full_version: StrictVersion,
        data: Union[Any, bytes, str],
    ) -> ProtoMessage:
        assert isinstance(data, (Any, bytes, str))

        msg_class = self.proto_messages.get((message_type, full_version.version[0]))
        if not msg_class:
            raise ValidationError(f"Protobuf message class not found for '{message_type}/{full_version.version[0]}'")

        try:
            if isinstance(data, Any):
                assert data.Is(msg_class.DESCRIPTOR)
                data_msg = msg_class()
                data.Unpack(data_msg)
            else:
                data_msg = self._decode_proto(msg_class, data)
        except (DecodeError, RuntimeError, AssertionError, json_format.ParseError) as e:
            raise ValidationError(f"Invalid data for message: {msg_class.__name__}: {e}")
        return data_msg

    def _encode_payload(
        self, meta_attrs: MetaAttributes, data: ProtoMessage, use_transport_attributes: bool
    ) -> Tuple[Union[bytes, str], dict]:
        assert isinstance(data, ProtoMessage)

        if not use_transport_attributes:
            msg = PayloadV1()
            msg.format_version = str(self._current_format_version)
            msg.id = str(meta_attrs.id)
            msg.metadata.publisher = meta_attrs.publisher
            msg.metadata.timestamp.FromMilliseconds(meta_attrs.timestamp)
            for k, v in meta_attrs.headers.items():
                msg.metadata.headers[k] = v
            msg.schema = meta_attrs.schema
            msg.data.Pack(data)
            payload = self._encode_proto(msg)
            msg_attrs = deepcopy(meta_attrs.headers)
        else:
            payload = self._encode_proto(data)
            msg_attrs = self._encode_meta_attributes(meta_attrs)
        return payload, msg_attrs

    def _encode_payload_firehose(
        self, message_type: str, version: StrictVersion, meta_attrs: MetaAttributes, data: ProtoMessage
    ) -> str:
        assert isinstance(data, ProtoMessage)

        msg = PayloadV1()
        msg.format_version = str(self._current_format_version)
        msg.id = str(meta_attrs.id)
        msg.metadata.publisher = meta_attrs.publisher
        msg.metadata.timestamp.FromMilliseconds(meta_attrs.timestamp)
        for k, v in meta_attrs.headers.items():
            msg.metadata.headers[k] = v
        msg.schema = meta_attrs.schema
        try:
            self._verify_known_minor_version(message_type, version)
            msg.data.Pack(data)
        except ValidationError:
            value_msg = Value()
            value_msg.string_value = base64.b64encode(data.SerializeToString()).decode()
            msg.data.Pack(value_msg)
        payload = encode_proto_json(msg)
        return payload

    def _check_schema(self, proto_messages) -> None:
        msg_types_found = {k for k in funcy.chain(settings.HEDWIG_MESSAGE_ROUTING, settings.HEDWIG_CALLBACKS)}
        errors = []
        for proto_message in proto_messages:
            message_type: Optional[str] = None
            major_version: int
            if options_pb2.message_options not in proto_message.DESCRIPTOR.GetOptions().Extensions:
                errors.append(f"Protobuf message class '{proto_message}' does not define option message_options")
            options = proto_message.DESCRIPTOR.GetOptions().Extensions[options_pb2.message_options]
            if not options.major_version:  # default is 0 which is invalid
                errors.append(
                    f"Protobuf message class '{proto_message}' does not define option message_options.major_version"
                )
                continue
            else:
                major_version = cast(int, options.major_version)
            if options.message_type:
                message_type = cast(str, options.message_type)
            m = self._message_name_re.match(proto_message.__name__)
            if m:
                name_message_type = m.group(1)
                name_major_version = int(m.group(2))
                if message_type is None:
                    message_type = name_message_type
                if name_major_version != major_version:
                    errors.append(
                        f"Protobuf message class '{proto_message}' mismatch in major version: '{name_major_version}' "
                        f"!= '{major_version}'"
                    )
            if not message_type:
                errors.append(f"Couldn't determine message type for Protobuf message class '{proto_message}'")
                continue
            if (message_type, major_version) in self.proto_messages:
                errors.append(f"Duplicate Protobuf message declared for '{message_type}/{major_version}'")
                continue
            self.proto_messages[(message_type, major_version)] = proto_message

        for message_type, version_pattern in msg_types_found:
            m = self._version_pattern_re.match(version_pattern)
            if not m:
                errors.append(f"Invalid version '{version_pattern}' for message: '{message_type}'")
                continue
            major_version = int(m.group(1))
            if major_version == 0:
                errors.append(f"Invalid version '{major_version}' for message: '{message_type}'. Must not be 0.")
            assert message_type  # mypy
            msg_class = self.proto_messages.get((message_type, major_version))
            if not msg_class:
                errors.append(
                    f"Invalid message_type, major version: '{message_type}/{major_version}', not found in declared "
                    f"messages"
                )
                continue

        if errors:
            raise SchemaError(str(errors))


class ProtobufJSONValidator(ProtobufValidator):
    """
    A validator that encodes the payload using Protobuf JSON format.
    Documentation: https://googleapis.dev/python/protobuf/latest/google/protobuf/json_format.html
    """

    def _decode_proto(self, msg_class: typing.Any, value: Union[str, bytes]) -> ProtoMessageT:  # type: ignore
        return decode_proto_json(msg_class, value)

    def _encode_proto(self, msg: ProtoMessage) -> Union[str, bytes]:
        return encode_proto_json(msg)
