import factory

from hedwig.testing.factories.base import BaseMessageFactory


class JSONSchemaDataFactory(factory.DictFactory):
    trip_id = 'T_1234567890123456'
    user_id = 'U_1234567890123456'
    device_id = 'abcdef00abcdef00abcdef00'
    vin = '00000000000000000'
    vehicle_id = 'C_1234567890123456'


class JSONSchemaMessageFactory(BaseMessageFactory):
    data = factory.SubFactory(JSONSchemaDataFactory)
