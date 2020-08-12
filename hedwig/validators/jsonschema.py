import json
import re
import typing
from decimal import Decimal
from distutils.version import StrictVersion
from pathlib import Path
from typing import Any, Tuple
from uuid import UUID

import funcy
from jsonschema import SchemaError, RefResolutionError, FormatChecker
from jsonschema.validators import Draft4Validator

from hedwig.conf import settings
from hedwig.exceptions import ValidationError
from hedwig.models import Message, Metadata
from hedwig.validators.base import HedwigBaseValidator


def _json_default(obj):
    if isinstance(obj, Decimal):
        int_val = int(obj)
        if int_val == obj:
            return int_val
        else:
            return float(obj)
    elif isinstance(obj, UUID):
        return str(obj)
    raise TypeError


class JSONSchemaValidator(HedwigBaseValidator):
    checker = FormatChecker()
    """
    FormatChecker that checks for `format` JSON-schema field. This may be customized by an app by overriding setting
    `HEDWIG_DATA_VALIDATOR_CLASS` and defining more format checkers.
    """

    schema: dict
    """
    The schema to validate data against - supplied by app
    """

    # uuid separated by hyphens:
    _human_uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

    _version_pattern_re = re.compile(r"^[0-9]+\.\*$")

    _validator: Draft4Validator

    _container_validator: Draft4Validator

    # schema parsing re, eg: hedwig.automatic.com/schema#/schemas/trip.created/1.0
    _schema_re = re.compile(r'([^/]+)/([^/]+)$')

    FORMAT_CURRENT_VERSION = StrictVersion('1.0')
    FORMAT_VERSIONS = [StrictVersion('1.0')]
    '''
    Here are the schema definitions:

    Version 1.0:
    {
        "format_version": "1.0",
        "schema": "https://hedwig.automatic.com/schema#/schemas/trip.created/1.0",
        "id": "b1328174-a21c-43d3-b303-964dfcc76efc",
        "metadata": {
            "timestamp": 1460868253255,
            "publisher": "myapp",
            "headers": {
                ...
            }
        },
        "data": {
            ...
        }
    }

    All the top-level fields (other than `metadata`) are required to be non-empty. `metadata` field is expected to
    be present, but may be empty. All fields in `metadata` are optional. `data` is validated using `schema`.
    '''

    def __init__(self, schema: typing.Optional[dict] = None) -> None:
        # automatically load schema
        container_schema_filepath = Path(__file__).resolve().parent / 'jsonschema_container_schema.json'
        with open(container_schema_filepath) as f:
            container_schema = json.load(f)

        self._container_validator = Draft4Validator(container_schema)

        if schema is None:
            # automatically load schema
            schema_filepath = settings.HEDWIG_SCHEMA_FILE
            with open(schema_filepath) as f:
                schema = json.load(f)

        self._check_schema(schema)

        self.schema = schema

        self._validator = Draft4Validator(schema, format_checker=self.checker)

    @property
    def schema_root(self) -> str:
        return self.schema['id']

    def deserialize(self, message_payload: str, provider_metadata: Any) -> Message:
        """
        Deserialize a message from the on-the-wire format
        :param message_payload: Raw message payload as received from the backend
        :param provider_metadata: Provider specific metadata
        :returns: Message object if valid
        :raise: :class:`hedwig.ValidationError` if validation fails.
        """
        try:
            message_data = json.loads(message_payload)
        except ValueError:
            raise ValidationError('not a valid JSON')
        errors = list(self._container_validator.iter_errors(message_data))
        if errors:
            raise ValidationError(errors)

        message_type, full_version = self._validate(message_data)

        return Message(
            id=message_data['id'],
            metadata=Metadata(
                timestamp=message_data['metadata']['timestamp'],
                headers=message_data['metadata']['headers'],
                publisher=message_data['metadata']['publisher'],
                provider_metadata=provider_metadata,
            ),
            data=message_data['data'],
            type=message_type,
            version=full_version,
        )

    def _validate(self, message_data: dict) -> Tuple[str, StrictVersion]:
        try:
            m = self._schema_re.search(message_data['schema'])
            if m is None:
                raise ValueError
            schema_groups = m.groups()
            message_type = schema_groups[0]
            full_version = StrictVersion(schema_groups[1])
        except (AttributeError, ValueError):
            raise ValidationError(f'Invalid schema found: {message_data["schema"]}')

        if not message_data['schema'].startswith(self.schema_root):
            raise ValidationError(f'message schema must start with "{self.schema_root}"')

        major_version = full_version.version[0]
        schema_ptr = message_data['schema'].replace(str(full_version), str(major_version)) + '.*'

        try:
            _, schema = self._validator.resolver.resolve(schema_ptr)
        except RefResolutionError:
            raise ValidationError('definition not found in schema')

        errors = list(self._validator.iter_errors(message_data['data'], schema))
        if errors:
            raise ValidationError(errors)
        return message_type, full_version

    def serialize(self, message: Message) -> str:
        data = {
            'format_version': str(self.FORMAT_CURRENT_VERSION),
            'schema': f'{self.schema_root}#/schemas/{message.type}/{message.version}',
            'id': message.id,
            'metadata': {'timestamp': message.timestamp, 'publisher': message.publisher, 'headers': message.headers},
            'data': message.data,
        }
        self._validate(data)
        return json.dumps(data, default=_json_default, allow_nan=False, separators=(',', ':'), indent=None)

    @classmethod
    def _check_schema(cls, schema: dict) -> None:
        msg_types_found = {k: False for k in funcy.chain(settings.HEDWIG_MESSAGE_ROUTING, settings.HEDWIG_CALLBACKS)}
        # custom validation for Hedwig - TODO ideally should just be represented in json-schema file as meta schema,
        # however jsonschema lib doesn't support draft 06 which is what's really required here
        errors = []
        if not schema.get('schemas'):
            errors.append("Invalid schema file: expected key 'schemas' with non-empty value")
        else:
            for msg_type, versions in schema['schemas'].items():
                if not isinstance(versions, dict) or not versions:
                    errors.append(
                        f"Invalid definition for message type: '{msg_type}', value must contain a dict of "
                        f"valid versions"
                    )
                else:
                    for version_pattern, definition in versions.items():
                        if not cls._version_pattern_re.match(version_pattern):
                            errors.append(f"Invalid version '{version_pattern}' for message type: '{msg_type}'")
                        if (msg_type, version_pattern) in msg_types_found:
                            msg_types_found[(msg_type, version_pattern)] = True
                        if not isinstance(definition, dict) and not definition:
                            errors.append(f"Invalid version '{version_pattern}' for message type: '{msg_type}'")

        for (msg_type, version_pattern), found in msg_types_found.items():
            if not found:
                errors.append(f"Schema not found for '{msg_type}' v{version_pattern}")

        if errors:
            raise SchemaError(str(errors))

    @staticmethod
    @FormatChecker.cls_checks('human-uuid')
    def _check_human_uuid(instance):
        if not isinstance(instance, str):
            return False
        return bool(JSONSchemaValidator._human_uuid_re.match(instance))
