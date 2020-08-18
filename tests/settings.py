import os


# to test callables in HEDWIG_CALLBACKS
def device_handler(message):
    pass


AWS_ACCESS_KEY = "DUMMY_KEY"
AWS_ACCOUNT_ID = "DUMMY_ACCOUNT"
AWS_REGION = "DUMMY_REGION"
AWS_SECRET_KEY = "DUMMY_SECRET"

AWS_CONNECT_TIMEOUT_S = 5
AWS_READ_TIMEOUT_S = 5

HEDWIG_QUEUE = 'DEV-MYAPP'

HEDWIG_JSONSCHEMA_FILE = os.path.abspath('tests/schemas/jsonschema.json')

HEDWIG_PROTOBUF_SCHEMA_MODULE = "tests.schemas.protos.protobuf_pb2"

HEDWIG_CALLBACKS = {
    ('trip_created', '1.*'): 'tests.handlers.trip_created_handler',
    ('trip_created', '2.*'): 'tests.handlers.trip_created_handler',
    ('device.created', '1.*'): device_handler,
}

HEDWIG_MESSAGE_ROUTING = {
    ('trip_created', '1.*'): 'dev-trip-created',
    ('trip_created', '2.*'): 'dev-trip-created',
    ('device.created', '1.*'): 'dev-device-created',
    ('vehicle_created', '1.*'): 'dev-vehicle-created',
}

HEDWIG_PUBLISHER = 'myapp'
