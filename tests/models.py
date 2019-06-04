from enum import Enum


class MessageType(Enum):
    trip_created = 'trip_created'
    device_created = 'device.created'
    vehicle_created = 'vehicle_created'
