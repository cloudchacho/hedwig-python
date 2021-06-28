from enum import Enum

import factory

from hedwig.testing.factories.base import BaseMessageFactory
from hedwig.validators.protobuf import ProtobufValidator


def data_creator(o):
    msg_type = o.msg_type
    if isinstance(msg_type, Enum):
        msg_type = msg_type.value
    msg_class = ProtobufValidator().proto_messages[(msg_type, o.model_version)]
    msg = msg_class()
    for attr in ('trip_id', 'user_id', 'device_id', 'vin', 'vehicle_id'):
        try:
            setattr(msg, attr, getattr(o, attr))
        except AttributeError:
            # field not present in msg
            pass
    return msg


class ProtobufMessageFactory(BaseMessageFactory):
    class Params:
        trip_id = 'T_1234567890123456'
        user_id = 'U_1234567890123456'
        device_id = 'abcdef00abcdef00abcdef00'
        vin = '00000000000000000'
        vehicle_id = 'C_1234567890123456'
        protobuf_schema_module = None  # required

    data = factory.LazyAttribute(data_creator)
