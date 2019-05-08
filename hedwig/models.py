import copy
import re
import time
import typing
import uuid
from distutils.version import StrictVersion
from enum import Enum

from hedwig.backends.utils import get_consumer_backend
from hedwig.conf import settings
from hedwig.exceptions import ValidationError, CallbackNotFound
from hedwig.validator import FormatValidator


MessageType = Enum(  # type: ignore
    'MessageType', {t[0].replace('.', '_').replace('-', '_'): t[0] for t in settings.HEDWIG_MESSAGE_ROUTING}
)

MessageType.__doc__ = (
    "Enumeration representing the message types supported for this service. This is automatically "
    "created based on setting `HEDWIG_MESSAGE_ROUTING`"
)

_validator = None


def _get_validator():
    global _validator
    if _validator is None:
        _validator = settings.HEDWIG_DATA_VALIDATOR_CLASS()
    return _validator


_format_validator = FormatValidator()


class Metadata:
    def __init__(self, data: dict) -> None:
        self._timestamp = data['timestamp']
        self._publisher = data['publisher']
        self._headers = data['headers']
        self._provider_metadata = None

    @property
    def timestamp(self) -> int:
        """
        Timestamp of message creation in epoch milliseconds
        """
        return self._timestamp

    @property
    def publisher(self) -> str:
        """
        Publisher of message
        """
        return self._publisher

    @property
    def provider_metadata(self):
        """
        Provider specific metadata, such as SQS Receipt, or Google ack id. This may be used to extend message
        visibility if the task is running longer than expected using :meth:`Message.extend_visibility_timeout`
        """
        return self._provider_metadata

    @provider_metadata.setter
    def provider_metadata(self, value) -> None:
        """
        Set the provider metadata
        """
        self._provider_metadata = value

    @property
    def headers(self) -> dict:
        """
        Custom headers sent with the message
        """
        return self._headers

    def as_dict(self) -> dict:
        return {"timestamp": self.timestamp, "headers": self.headers, "publisher": self.publisher}

    def __eq__(self, other) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.as_dict() == typing.cast(Metadata, other).as_dict()


class Message:
    """
    Model for Hedwig messages. All properties of a message should be considered immutable.
    A Message object will always have known message format schema and message format schema version even if the data
    _may_ not be valid.
    """

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

    # schema parsing re, eg: hedwig.automatic.com/schema#/schemas/trip.created/1.0
    _schema_re = re.compile(r'([^/]+)/([^/]+)$')

    def __init__(self, data: dict) -> None:
        """
        See message format version definitions above
        """
        _format_validator.validate(data)

        self._id = data['id']
        self._metadata = Metadata(data['metadata'])
        self._schema = data['schema']
        self._data = data['data']
        self._format_version = StrictVersion(data['format_version'])

        self.validate()

    def validate(self) -> None:
        """
        Validates a message using JSON schema.

        :raise: :class:`hedwig.ValidationError` if validation fails.
        """
        try:
            mo = self._schema_re.search(self.schema)
            if mo is None:
                raise ValueError
            schema_groups = mo.groups()
            self._type = MessageType(schema_groups[0])
            self._data_schema_version = StrictVersion(schema_groups[1])
        except (AttributeError, ValueError):
            raise ValidationError(f'Invalid schema found: {self.schema}')

        _get_validator().validate(self)

    def validate_callback(self) -> None:
        from hedwig.callback import Callback

        try:
            self._callback = Callback.find_by_message(self.type, self.data_schema_version.version[0])
        except CallbackNotFound:
            raise ValidationError

    def exec_callback(self) -> None:
        """
        Call the callback with this message
        """
        self.callback.call(self)

    @classmethod
    def _create_metadata(cls, headers: dict) -> dict:
        return {'timestamp': int(time.time() * 1000), 'publisher': settings.HEDWIG_PUBLISHER, 'headers': headers}

    @classmethod
    def new(
        cls,
        msg_type: MessageType,
        data_schema_version: StrictVersion,
        data: dict,
        msg_id: str = None,
        headers: dict = None,
    ) -> 'Message':
        """
        Creates Message object given type, data schema version and data. This is typically used by the publisher code.

        :param msg_type: MessageType instance
        :param data_schema_version: StrictVersion representing data schema
        :param data: The dict to pass in `data` field of Message.
        :param msg_id: Custom message identifier. If not passed, a randomly generated uuid will be used.
        :param headers: Custom headers
        """
        assert isinstance(msg_type, MessageType)
        assert isinstance(data_schema_version, StrictVersion)
        assert isinstance(data, dict)
        assert isinstance(msg_id, (type(None), str))
        assert isinstance(headers, (type(None), dict))

        return Message(
            data={
                'format_version': str(cls.FORMAT_CURRENT_VERSION),
                'id': msg_id or str(uuid.uuid4()),
                'schema': f'{_get_validator().schema_root}#/schemas/{msg_type.value}/{data_schema_version}',
                'metadata': cls._create_metadata(headers or {}),
                'data': copy.deepcopy(data),
            }
        )

    def publish(self):
        """
        Publish this message on Hedwig infra
        """
        from hedwig.publisher import publish

        publish(self)

    def extend_visibility_timeout(self, visibility_timeout_s: int) -> None:
        """
        Extends visibility timeout of a message for long running tasks.
        """
        consumer_backend = get_consumer_backend()
        consumer_backend.extend_visibility_timeout(visibility_timeout_s, self.provider_metadata)

    def __eq__(self, other) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.as_dict() == typing.cast(Message, other).as_dict()

    @property
    def data_schema_version(self) -> StrictVersion:
        """
        `StrictVersion` object representing data schema version. May be `None` if message can't be validated.
        """
        return self._data_schema_version

    @property
    def callback(self):
        return self._callback

    @property
    def id(self) -> str:
        """
        Message identifier
        """
        return self._id

    @property
    def schema(self) -> str:
        """
        Message schema
        """
        return self._schema

    @property
    def type(self) -> MessageType:
        """
        MessageType. May be none if message is invalid
        """
        return self._type

    @property
    def format_version(self) -> StrictVersion:
        """
        Message format version (this is different from data schema version)
        """
        return self._format_version

    @property
    def metadata(self) -> Metadata:
        """
        Message metadata
        """
        return self._metadata

    @property
    def timestamp(self) -> int:
        return self.metadata.timestamp

    timestamp.__doc__ = Metadata.timestamp.__doc__

    @property
    def headers(self) -> dict:
        return self._metadata.headers

    headers.__doc__ = Metadata.headers.__doc__

    @property
    def provider_metadata(self):
        return self.metadata.provider_metadata

    provider_metadata.__doc__ = Metadata.provider_metadata.__doc__

    @property
    def publisher(self) -> typing.Optional[str]:
        return self.metadata.publisher

    publisher.__doc__ = Metadata.publisher.__doc__

    @property
    def data(self) -> dict:
        """
        Message data
        """
        return self._data

    @property
    def topic(self) -> str:
        """
        The SNS topic name for routing the message
        """
        version_pattern = f'{self.data_schema_version.version[0]}.*'
        return settings.HEDWIG_MESSAGE_ROUTING[(self.type.value, version_pattern)]

    def as_dict(self) -> dict:
        return {
            'id': self.id,
            'format_version': str(self.format_version),
            'schema': self.schema,
            'metadata': self.metadata.as_dict(),
            'data': self.data,
        }

    def __repr__(self) -> str:
        return f'<Message type={self.type.value}/{self.format_version}>'
