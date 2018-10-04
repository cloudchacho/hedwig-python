import time
import typing
import uuid

import factory
from factory import fuzzy

from hedwig.models import Message, MessageType
from hedwig.conf import settings


class HeadersFactory(factory.DictFactory):
    request_id = factory.Faker('uuid4')


class MetadataFactory(factory.DictFactory):
    timestamp = factory.LazyFunction(lambda: int(time.time() * 1000))
    publisher = settings.HEDWIG_PUBLISHER
    headers = factory.SubFactory(HeadersFactory)


class DataFactory(factory.DictFactory):
    trip_id = 'T_1234567890123456'
    user_id = 'U_1234567890123456'
    device_id = 'abcdef00abcdef00abcdef00'
    vin = '00000000000000000'
    vehicle_id = 'C_1234567890123456'


_SCHEMA_FORMAT = 'https://hedwig.automatic.com/schema#/schemas/{}/{}.{}'


class MessageFactory(factory.DictFactory):
    class Meta:
        model = Message

    class Params:
        model_version = 1
        addition_version = 0
        msg_type = fuzzy.FuzzyChoice(list(MessageType))

    format_version = str(Message.FORMAT_CURRENT_VERSION)
    schema = factory.LazyAttribute(
        lambda obj: _SCHEMA_FORMAT.format(obj.msg_type.value, obj.model_version, obj.addition_version)
    )
    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    metadata = factory.SubFactory(MetadataFactory)
    data = factory.SubFactory(DataFactory)

    @classmethod
    def _build(cls, model_class: typing.Type[Message], *args, **kwargs) -> typing.Dict:
        if args:
            raise ValueError("MessageFactory %r does not support Meta.inline_args.", cls)

        return kwargs

    @classmethod
    def _create(cls, model_class: typing.Type[Message], *args, **kwargs) -> Message:
        return model_class(cls._build(model_class, *args, **kwargs))
