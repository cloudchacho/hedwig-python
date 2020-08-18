import json
import re
import typing
from copy import deepcopy
from decimal import Decimal
from distutils.version import StrictVersion
from pathlib import Path
from typing import Tuple, Union
from uuid import UUID

import funcy
from jsonschema import SchemaError, RefResolutionError, FormatChecker
from jsonschema.validators import Draft4Validator

from hedwig.conf import settings
from hedwig.exceptions import ValidationError
from hedwig.validators.base import HedwigBaseValidator, MetaAttributes


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

        if not settings.HEDWIG_USE_TRANSPORT_MESSAGE_ATTRIBUTES:
            self._container_validator = Draft4Validator(container_schema)

        if schema is None:
            # automatically load schema
            schema_filepath = settings.HEDWIG_JSONSCHEMA_FILE
            with open(schema_filepath) as f:
                schema = json.load(f)

        self._check_schema(schema)

        self.schema = schema

        self._validator = Draft4Validator(schema, format_checker=self.checker)

        # schema encoding, eg: hedwig.automatic.com/schema#/schemas/trip.created/1.0
        schema_fmt = f'{self.schema_root}#/schemas/{{message_type}}/{{message_version}}'
        schema_re = re.compile(r'([^/]+)/([^/]+)$')

        super().__init__(
            schema_fmt, schema_re, StrictVersion('1.0'),
        )

    @property
    def schema_root(self) -> str:
        return self.schema['id']

    def _extract_data(self, message_payload: Union[str, bytes], attributes: dict) -> Tuple[MetaAttributes, dict]:
        assert isinstance(message_payload, str)

        try:
            payload = json.loads(message_payload)
        except ValueError:
            raise ValidationError('not a valid JSON')

        if not settings.HEDWIG_USE_TRANSPORT_MESSAGE_ATTRIBUTES:
            errors = list(self._container_validator.iter_errors(payload))
            if errors:
                raise ValidationError(errors)

            data = payload['data']
            meta_attrs = MetaAttributes(
                payload['metadata']['timestamp'],
                payload['metadata']['publisher'],
                payload['metadata']['headers'],
                payload['id'],
                payload['schema'],
                payload['format_version'],
            )
        else:
            data = payload
            meta_attrs = self._decode_meta_attributes(attributes)
            if meta_attrs.format_version != self._current_format_version:
                raise ValidationError(f"Invalid format version: {meta_attrs.format_version}")
        return meta_attrs, data

    def _decode_data(
        self, meta_attrs: MetaAttributes, message_type: str, full_version: StrictVersion, data: dict
    ) -> dict:
        if not meta_attrs.schema.startswith(self.schema_root):
            raise ValidationError(f'message schema must start with "{self.schema_root}"')
        major_version = full_version.version[0]
        schema_ptr = meta_attrs.schema.replace(str(full_version), str(major_version)) + '.*'

        try:
            _, schema = self._validator.resolver.resolve(schema_ptr)
        except RefResolutionError:
            raise ValidationError(f'Definition not found in schema: {schema_ptr}')

        errors = list(self._validator.iter_errors(data, schema))
        if errors:
            raise ValidationError(errors)
        return data

    def _encode_data(self, data: dict) -> dict:
        assert isinstance(data, dict)
        # will get encoded in _encode_payload
        return data

    def _encode_payload(self, meta_attrs: MetaAttributes, data: dict) -> Tuple[str, dict]:
        if not settings.HEDWIG_USE_TRANSPORT_MESSAGE_ATTRIBUTES:
            payload = {
                'format_version': str(self._current_format_version),
                'schema': meta_attrs.schema,
                'id': meta_attrs.id,
                'metadata': {
                    'timestamp': meta_attrs.timestamp,
                    'publisher': meta_attrs.publisher,
                    'headers': meta_attrs.headers,
                },
                'data': data,
            }
            msg_attrs = deepcopy(meta_attrs.headers)
        else:
            payload = data
            msg_attrs = self._encode_meta_attributes(meta_attrs)
        return (
            json.dumps(payload, default=_json_default, allow_nan=False, separators=(',', ':'), indent=None),
            msg_attrs,
        )

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
