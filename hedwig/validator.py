from distutils.version import StrictVersion
import json
from pathlib import Path
import re

import funcy
from jsonschema import SchemaError, RefResolutionError, FormatChecker
from jsonschema.validators import Draft4Validator

from hedwig.conf import settings
from hedwig.exceptions import ValidationError


class MessageValidator(Draft4Validator):
    # uuid separated by hyphens:
    _human_uuid_re = re.compile("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

    checker = FormatChecker()
    """
    FormatChecker that checks for `format` JSON-schema field. This may be customized by an app by overriding setting
    `HEDWIG_DATA_VALIDATOR_CLASS` and defining more format checkers.
    """

    def __init__(self, schema: dict = None):
        if not schema:
            # automatically load schema
            schema_filepath = settings.HEDWIG_SCHEMA_FILE
            with open(schema_filepath) as f:
                schema = json.load(f)

        super(MessageValidator, self).__init__(schema, format_checker=self.checker)

    @property
    def schema_root(self) -> str:
        return self.schema['id']

    def validate(self, message: 'hedwig.Message') -> None:
        """
        Validates a message using JSON Schema
        """
        if not message.schema.startswith(self.schema_root):
            raise ValidationError

        full_version = StrictVersion(message.schema.split('/')[-1])
        major_version = full_version.version[0]
        major_only_schema_ptr = message.schema.replace(str(full_version), str(major_version))

        try:
            _, schema = self.resolver.resolve(major_only_schema_ptr)
        except RefResolutionError:
            raise ValidationError

        errors = list(self.iter_errors(message.data, schema))
        if errors:
            raise ValidationError(errors)

    @classmethod
    def check_schema(cls, schema: dict) -> None:
        super(MessageValidator, cls).check_schema(schema)

        msg_types_found = {k: False for k in funcy.chain(settings.HEDWIG_MESSAGE_ROUTING, settings.HEDWIG_CALLBACKS)}
        # custom validation for Hedwig - TODO ideally should just be represented in json-schema file as meta schema,
        # however jsonschema lib doesn't support draft 06 which is what's really required here
        errors = []
        if not schema.get('schemas'):
            errors.append("Invalid schema file: expected key 'schemas' with non-empty value")
        else:
            for msg_type, versions in schema['schemas'].items():
                if not isinstance(versions, dict) or not versions:
                    errors.append(f"Invalid definition for message type: '{msg_type}', value must contain a dict of "
                                  f"valid versions")
                else:
                    for major_version, definition in versions.items():
                        try:
                            if (msg_type, int(major_version)) in msg_types_found:
                                msg_types_found[(msg_type, int(major_version))] = True
                        except ValueError:
                            errors.append(f"Invalid version '{major_version}' for message type: '{msg_type}'")

        for (msg_type, major_version), found in msg_types_found.items():
            if not found:
                errors.append(f"Schema not found for '{msg_type}' v{major_version}")

        if errors:
            raise SchemaError(errors)

    @staticmethod
    @FormatChecker.cls_checks('human-uuid')
    def check_human_uuid(instance):
        if not isinstance(instance, str):
            return True
        return bool(MessageValidator._human_uuid_re.match(instance))


class FormatValidator(Draft4Validator):
    def __init__(self):
        # automatically load schema
        schema_filepath = Path(__file__).resolve().parent / 'format_schema.json'
        with open(schema_filepath) as f:
            schema = json.load(f)

        super(FormatValidator, self).__init__(schema)

    def validate(self, data: dict) -> None:
        errors = list(self.iter_errors(data))
        if errors:
            raise ValidationError(errors)
