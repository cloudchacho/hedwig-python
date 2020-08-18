from hedwig.testing.factories.protobuf import ProtobufMessageFactory as BaseProtobufMessageFactory
from tests.schemas.protos import protobuf_pb2


class ProtobufMessageFactory(BaseProtobufMessageFactory):
    class Params:
        protobuf_schema_module = protobuf_pb2
