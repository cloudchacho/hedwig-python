import json
from collections import namedtuple
from distutils.version import StrictVersion
from typing import Any, Tuple

from hedwig.conf import settings
from hedwig.exceptions import ValidationError
from hedwig.models import Message


MetaAttributes = namedtuple('MetaAttributes', ['timestamp', 'publisher', 'headers', 'id', 'schema', 'format_version'])


class HedwigBaseValidator:
    """
    Base class responsible for serializing / encoding and deserializing / decoding messages into / from format on the
    wire.
    """

    def deserialize(self, message_payload: str, attributes: dict, provider_metadata: Any) -> Message:
        """
        Deserialize a message from the on-the-wire format
        :param message_payload: Raw message payload as received from the backend
        :param provider_metadata: Provider specific metadata
        :param attributes: Message attributes from the transport backend
        :returns: Message object if valid
        :raise: :class:`hedwig.ValidationError` if validation fails.
        """
        raise NotImplementedError

    def serialize(self, message: Message) -> Tuple[str, dict]:
        """
        Serialize a message for appropriate on-the-wire format
        :return: Tuple of message payload and transport attributes
        """
        raise NotImplementedError

    def _decode_meta_attributes(self, attributes: dict) -> MetaAttributes:
        """
        Decodes meta attributes from transport attributes
        :param attributes: Message attributes from the transport backend
        :return:
        """
        assert settings.HEDWIG_USE_TRANSPORT_MESSAGE_ATTRIBUTES

        for attr in (
            'hedwig_format_version',
            'hedwig_headers',
            'hedwig_id',
            'hedwig_message_timestamp',
            'hedwig_publisher',
            'hedwig_schema',
        ):
            value = attributes.get(attr)
            if not isinstance(value, str):
                raise ValidationError(f"Invalid message attribute: {attr} must be string, found: {value}")

        return MetaAttributes(
            int(attributes['hedwig_message_timestamp']),
            attributes['hedwig_publisher'],
            json.loads(attributes['hedwig_headers']),
            attributes['hedwig_id'],
            attributes['hedwig_schema'],
            StrictVersion(attributes['hedwig_format_version']),
        )

    def _encode_meta_attributes(self, meta_attrs: MetaAttributes) -> dict:
        """
        Encodes meta attributes as transport attributes
        :param meta_attrs:
        :return:
        """
        assert settings.HEDWIG_USE_TRANSPORT_MESSAGE_ATTRIBUTES

        return {
            'hedwig_format_version': str(meta_attrs.format_version),
            'hedwig_headers': json.dumps(meta_attrs.headers, allow_nan=False, separators=(',', ':'), indent=None),
            'hedwig_id': str(meta_attrs.id),
            'hedwig_message_timestamp': str(meta_attrs.timestamp),
            'hedwig_publisher': meta_attrs.publisher,
            'hedwig_schema': meta_attrs.schema,
        }
