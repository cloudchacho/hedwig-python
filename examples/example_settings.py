import os

HEDWIG_CALLBACKS = {('user-created', '1.*'): 'callbacks.user_created_handler'}

HEDWIG_MESSAGE_ROUTING = {('user-created', '1.*'): 'dev-user-created-v1'}

HEDWIG_PROTOBUF = os.environ.get('HEDWIG_PROTOBUF', 'false').lower() == 'true'

if HEDWIG_PROTOBUF:
    HEDWIG_PROTOBUF_MESSAGES = ['protos.schema_pb2.UserCreatedV1', 'protos.schema_pb2.UserUpdatedV1']
    HEDWIG_DATA_VALIDATOR_CLASS = 'hedwig.validators.protobuf.ProtobufValidator'
else:
    HEDWIG_JSONSCHEMA_FILE = 'schema.json'

HEDWIG_PUBLISHER = 'myapp'

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
