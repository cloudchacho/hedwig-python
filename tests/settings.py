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

HEDWIG_PROTOBUF_MESSAGES = [
    "tests.schemas.protos.protobuf_pb2.TripCreatedV1",
    "tests.schemas.protos.protobuf_pb2.TripCreatedV2",
    "tests.schemas.protos.protobuf_pb2.DeviceCreatedV1",
    "tests.schemas.protos.protobuf_pb2.VehicleCreatedV1",
]

HEDWIG_CALLBACKS = {
    ('trip_created', '1.*'): 'tests.handlers.trip_created_handler',
    ('trip_created', '2.*'): 'tests.handlers.trip_created_handler',
    ('device.created', '1.*'): device_handler,
}

HEDWIG_MESSAGE_ROUTING = {
    ('trip_created', '1.*'): 'dev-trip-created-v1',
    ('trip_created', '2.*'): 'dev-trip-created-v2',
    ('device.created', '1.*'): 'dev-device-created-v1',
    ('vehicle_created', '1.*'): ('dev-vehicle-created-v1', 'project-id-or-account-id'),
}

HEDWIG_PUBLISHER = 'myapp'
