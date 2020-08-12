import time
import typing
import uuid
from distutils.version import StrictVersion
from enum import Enum

import factory

from hedwig.models import Message, Metadata
from hedwig.conf import settings


class HeadersFactory(factory.DictFactory):
    request_id = factory.Faker('uuid4')


class MetadataFactory(factory.Factory):
    class Meta:
        model = Metadata

    timestamp = factory.LazyFunction(lambda: int(time.time() * 1000))
    publisher = settings.HEDWIG_PUBLISHER
    headers = factory.SubFactory(HeadersFactory)

    @classmethod
    def _build(cls, model_class: typing.Type[Message], *args, **kwargs) -> typing.Dict:
        if args:
            raise ValueError("MessageFactory %r does not support Meta.inline_args.", cls)

        return kwargs


class DataFactory(factory.DictFactory):
    trip_id = 'T_1234567890123456'
    user_id = 'U_1234567890123456'
    device_id = 'abcdef00abcdef00abcdef00'
    vin = '00000000000000000'
    vehicle_id = 'C_1234567890123456'


_SCHEMA_FORMAT = 'https://hedwig.automatic.com/schema#/schemas/{}/{}.{}'


class MessageFactory(factory.Factory):
    class Meta:
        model = Message

    class Params:
        model_version = 1
        addition_version = 0
        msg_type = None  # required

    version = factory.LazyAttribute(lambda obj: StrictVersion(f'{obj.model_version}.{obj.addition_version}'))
    type = factory.LazyAttribute(lambda obj: obj.msg_type.value if isinstance(obj.msg_type, Enum) else obj.msg_type)
    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    metadata = factory.SubFactory(MetadataFactory)
    data = factory.SubFactory(DataFactory)

    @classmethod
    def _build(cls, model_class: typing.Type[Message], *args, **kwargs) -> typing.Dict:
        if args:
            raise ValueError("MessageFactory %r does not support Meta.inline_args.", cls)

        return kwargs
