import abc
from collections import namedtuple
from distutils.version import StrictVersion
from typing import Any, Tuple, Union, Dict, Pattern

from hedwig.conf import settings
from hedwig.exceptions import ValidationError
from hedwig.models import Message, Metadata

MetaAttributes = namedtuple('MetaAttributes', ['timestamp', 'publisher', 'headers', 'id', 'schema', 'format_version'])


class HedwigBaseValidator:
    """
    Base class responsible for serializing / encoding and deserializing / decoding messages into / from format on the
    wire.
    """

    _schema_re: Pattern
    """
    A regex that matches encoded schema and matches 2 groups: message_type, message_version
    """

    _schema_fmt: str
    """
    A f-string that is used to encode schema that contains two placeholders: message_type, message_version
    """

    _current_format_version: StrictVersion

    def __init__(self, schema_fmt: str, schema_re: Pattern, current_format_version: StrictVersion):
        self._schema_fmt = schema_fmt
        self._schema_re = schema_re
        self._current_format_version = current_format_version

    @abc.abstractmethod
    def _extract_data(
        self, message_payload: Union[str, bytes], attributes: dict, use_transport_attributes: bool
    ) -> Tuple[MetaAttributes, Any]:
        """
        Extracts data from the on-the-wire payload
        """

    @abc.abstractmethod
    def _extract_data_firehose(self, line: str) -> Tuple[MetaAttributes, Any]:
        """
        Extracts data from firehose line
        """

    @abc.abstractmethod
    def _decode_data(
        self,
        meta_attrs: MetaAttributes,
        message_type: str,
        full_version: StrictVersion,
        data: Any,
    ) -> Any:
        """
        Validates decoded data
        """

    def _encode_message_type(self, message_type: str, version: StrictVersion) -> str:
        """
        Encodes message type in outgoing message attribute
        """
        return self._schema_fmt.format(message_type=message_type, message_version=version)

    def _decode_message_type(self, schema: str) -> Tuple[str, StrictVersion]:
        """
        Decode message type from meta attributes
        """
        try:
            m = self._schema_re.search(schema)
            if m is None:
                raise ValueError
            schema_groups = m.groups()
            message_type = schema_groups[0]
            full_version = StrictVersion(schema_groups[1])
        except (AttributeError, ValueError):
            raise ValidationError(f'Invalid schema found: {schema}')
        return message_type, full_version

    def _verify_known_minor_version(self, message_type: str, full_version: StrictVersion):
        """
        Validate that minor version is known
        """
        raise NotImplementedError

    def _verify_headers(self, headers: dict):
        """
        Validate headers are sane
        """
        for k, v in headers.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise ValidationError(f"Invalid header key or value: '{k}': '{v}' - must be strings")
            if k.startswith("hedwig_"):
                raise ValidationError(f"Invalid header key: '{k}' - can't begin with reserved namespace 'hedwig_'")

    def _deserialize(
        self,
        message_payload: Union[str, bytes],
        attributes: dict,
        provider_metadata: Any,
        use_transport_attributes: bool,
    ) -> Message:
        """
        Deserialize a message from the on-the-wire format
        :param message_payload: Raw message payload as received from the backend
        :param provider_metadata: Provider specific metadata
        :param attributes: Message attributes from the transport backend
        :returns: Message object if valid
        :raise: :class:`hedwig.ValidationError` if validation fails.
        """
        meta_attrs, extracted_data = self._extract_data(message_payload, attributes, use_transport_attributes)
        self._verify_headers(meta_attrs.headers)
        message_type, version = self._decode_message_type(meta_attrs.schema)
        data = self._decode_data(meta_attrs, message_type, version, extracted_data)

        return Message(
            id=meta_attrs.id,
            metadata=Metadata(
                timestamp=meta_attrs.timestamp,
                headers=meta_attrs.headers,
                publisher=meta_attrs.publisher,
                provider_metadata=provider_metadata,
            ),
            data=data,
            type=message_type,
            version=version,
        )

    def deserialize(self, message_payload: Union[str, bytes], attributes: dict, provider_metadata: Any) -> Message:
        """
        Deserialize a message from the on-the-wire format
        :param message_payload: Raw message payload as received from the backend
        :param provider_metadata: Provider specific metadata
        :param attributes: Message attributes from the transport backend
        :returns: Message object if valid
        :raise: :class:`hedwig.ValidationError` if validation fails.
        """
        return self._deserialize(
            message_payload, attributes, provider_metadata, settings.HEDWIG_USE_TRANSPORT_MESSAGE_ATTRIBUTES
        )

    def deserialize_containerized(self, message_payload: Union[str, bytes]) -> Message:
        """
        Deserialize a message assuming containerized format regardless of configured setting.
        :param message_payload: Raw message payload as received from the backend
        :returns: Message object if valid
        :raise: :class:`hedwig.ValidationError` if validation fails.
        """
        return self._deserialize(message_payload, {}, None, False)

    def deserialize_firehose(self, line: str) -> Message:
        """
        Deserialize a message from a line in firehose file. This is slightly different from on-the-wire format:

        1. It always uses container format (i.e. HEDWIG_USE_TRANSPORT_MESSAGE_ATTRIBUTES is ignored)
        2. For binary file formats, its possible data is encoded as binary base64 blob rather than JSON.
        3. Known minor versions isn't verified - knowing major version schema is good enough to read firehose.

        :param line: Raw line read from firehose file
        :returns: Message object if valid
        :raise: :class:`hedwig.ValidationError` if validation fails.
        """
        meta_attrs, extracted_data = self._extract_data_firehose(line)
        message_type, version = self._decode_message_type(meta_attrs.schema)
        data = self._decode_data(meta_attrs, message_type, version, extracted_data)

        return Message(
            id=meta_attrs.id,
            metadata=Metadata(
                timestamp=meta_attrs.timestamp,
                headers=meta_attrs.headers,
                publisher=meta_attrs.publisher,
                provider_metadata=None,
            ),
            data=data,
            type=message_type,
            version=version,
        )

    def _encode_payload(
        self, meta_attrs: MetaAttributes, data: Any, use_transport_attributes: bool
    ) -> Tuple[Union[str, bytes], dict]:
        """
        Encodes on-the-wire payload
        """
        raise NotImplementedError

    def _encode_payload_firehose(
        self, message_type: str, version: StrictVersion, meta_attrs: MetaAttributes, data: Any
    ) -> str:
        """
        Encodes firehose line
        """
        raise NotImplementedError

    def _serialize(self, message: Message, use_transport_attributes: bool) -> Tuple[Union[str, bytes], dict]:
        self._verify_known_minor_version(message.type, message.version)
        self._verify_headers(message.headers)
        schema = self._encode_message_type(message.type, message.version)
        meta_attrs = MetaAttributes(
            message.timestamp,
            message.publisher,
            message.headers,
            message.id,
            schema,
            self._current_format_version,
        )
        message_payload, msg_attrs = self._encode_payload(meta_attrs, message.data, use_transport_attributes)
        # validate payload from scratch before publishing
        self._deserialize(message_payload, msg_attrs, None, use_transport_attributes)
        return message_payload, msg_attrs

    def serialize(self, message: Message) -> Tuple[Union[str, bytes], dict]:
        """
        Serialize a message for appropriate on-the-wire format
        :return: Tuple of message payload and transport attributes
        """
        return self._serialize(message, settings.HEDWIG_USE_TRANSPORT_MESSAGE_ATTRIBUTES)

    def serialize_containerized(self, message: Message) -> Union[str, bytes]:
        """
        Serialize a message using containerized format regardless of configured settings. In most cases, you just want
        to use `.serialize`.
        :return: Message payload
        """
        return self._serialize(message, False)[0]

    def serialize_firehose(self, message: Message) -> str:
        """
        Serialize a message for appropriate firehose file format. See
        :meth:`hedwig.validators.base.HedwigBaseValidator.deserialize_firehose` for details.
        :return: Tuple of message payload and transport attributes
        """
        schema = self._encode_message_type(message.type, message.version)
        meta_attrs = MetaAttributes(
            message.timestamp,
            message.publisher,
            message.headers,
            message.id,
            schema,
            self._current_format_version,
        )
        message_payload = self._encode_payload_firehose(message.type, message.version, meta_attrs, message.data)
        # validate payload from scratch
        self.deserialize_firehose(message_payload)
        return message_payload

    def _decode_meta_attributes(self, attributes: Dict[str, str]) -> MetaAttributes:
        """
        Decodes meta attributes from transport attributes
        :param attributes: Message attributes from the transport backend
        :return:
        """
        assert settings.HEDWIG_USE_TRANSPORT_MESSAGE_ATTRIBUTES

        for attr in (
            'hedwig_format_version',
            'hedwig_id',
            'hedwig_message_timestamp',
            'hedwig_publisher',
            'hedwig_schema',
        ):
            value = attributes.get(attr)
            if not isinstance(value, str):
                raise ValidationError(f"Invalid message attribute: {attr} must be string, found: {value}")

        headers = {k: v for k, v in attributes.items() if not k.startswith("hedwig_")}
        return MetaAttributes(
            int(attributes['hedwig_message_timestamp']),
            attributes['hedwig_publisher'],
            headers,
            attributes['hedwig_id'],
            attributes['hedwig_schema'],
            StrictVersion(attributes['hedwig_format_version']),
        )

    def _encode_meta_attributes(self, meta_attrs: MetaAttributes) -> Dict[str, str]:
        """
        Encodes meta attributes as transport attributes
        :param meta_attrs:
        :return:
        """
        assert settings.HEDWIG_USE_TRANSPORT_MESSAGE_ATTRIBUTES

        attrs = {
            'hedwig_format_version': str(meta_attrs.format_version),
            'hedwig_id': str(meta_attrs.id),
            'hedwig_message_timestamp': str(meta_attrs.timestamp),
            'hedwig_publisher': meta_attrs.publisher,
            'hedwig_schema': meta_attrs.schema,
        }
        attrs.update(meta_attrs.headers)
        return attrs
