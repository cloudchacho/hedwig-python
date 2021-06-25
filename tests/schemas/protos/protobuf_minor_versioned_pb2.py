# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: protobuf_minor_versioned.proto

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from hedwig.protobuf import options_pb2 as hedwig_dot_protobuf_dot_options__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='protobuf_minor_versioned.proto',
  package='tests.minor_versioned',
  syntax='proto2',
  serialized_options=None,
  create_key=_descriptor._internal_create_key,
  serialized_pb=b'\n\x1eprotobuf_minor_versioned.proto\x12\x15tests.minor_versioned\x1a\x1dhedwig/protobuf/options.proto\"O\n\rTripCreatedV1\x12\x12\n\nvehicle_id\x18\x01 \x02(\t\x12\x0f\n\x07user_id\x18\x02 \x02(\t\x12\x0b\n\x03vin\x18\x03 \x02(\t:\x0c\x9a\x82\x19\x02\x08\x01\x9a\x82\x19\x02\x10\x01\"8\n\rTripCreatedV2\x12\x12\n\nvehicle_id\x18\x01 \x02(\t\x12\x0b\n\x03vin\x18\x02 \x02(\t:\x06\x9a\x82\x19\x02\x08\x02\"=\n\x0f\x44\x65viceCreatedV1\x12\x11\n\tdevice_id\x18\x01 \x02(\t\x12\x0f\n\x07user_id\x18\x02 \x02(\t:\x06\x9a\x82\x19\x02\x08\x01\".\n\x10VehicleCreatedV1\x12\x12\n\nvehicle_id\x18\x01 \x02(\t:\x06\x9a\x82\x19\x02\x08\x01'
  ,
  dependencies=[hedwig_dot_protobuf_dot_options__pb2.DESCRIPTOR,])




_TRIPCREATEDV1 = _descriptor.Descriptor(
  name='TripCreatedV1',
  full_name='tests.minor_versioned.TripCreatedV1',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='vehicle_id', full_name='tests.minor_versioned.TripCreatedV1.vehicle_id', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=b"".decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='user_id', full_name='tests.minor_versioned.TripCreatedV1.user_id', index=1,
      number=2, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=b"".decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='vin', full_name='tests.minor_versioned.TripCreatedV1.vin', index=2,
      number=3, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=b"".decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=b'\232\202\031\002\010\001\232\202\031\002\020\001',
  is_extendable=False,
  syntax='proto2',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=88,
  serialized_end=167,
)


_TRIPCREATEDV2 = _descriptor.Descriptor(
  name='TripCreatedV2',
  full_name='tests.minor_versioned.TripCreatedV2',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='vehicle_id', full_name='tests.minor_versioned.TripCreatedV2.vehicle_id', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=b"".decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='vin', full_name='tests.minor_versioned.TripCreatedV2.vin', index=1,
      number=2, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=b"".decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=b'\232\202\031\002\010\002',
  is_extendable=False,
  syntax='proto2',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=169,
  serialized_end=225,
)


_DEVICECREATEDV1 = _descriptor.Descriptor(
  name='DeviceCreatedV1',
  full_name='tests.minor_versioned.DeviceCreatedV1',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='device_id', full_name='tests.minor_versioned.DeviceCreatedV1.device_id', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=b"".decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='user_id', full_name='tests.minor_versioned.DeviceCreatedV1.user_id', index=1,
      number=2, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=b"".decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=b'\232\202\031\002\010\001',
  is_extendable=False,
  syntax='proto2',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=227,
  serialized_end=288,
)


_VEHICLECREATEDV1 = _descriptor.Descriptor(
  name='VehicleCreatedV1',
  full_name='tests.minor_versioned.VehicleCreatedV1',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='vehicle_id', full_name='tests.minor_versioned.VehicleCreatedV1.vehicle_id', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=b"".decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=b'\232\202\031\002\010\001',
  is_extendable=False,
  syntax='proto2',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=290,
  serialized_end=336,
)

DESCRIPTOR.message_types_by_name['TripCreatedV1'] = _TRIPCREATEDV1
DESCRIPTOR.message_types_by_name['TripCreatedV2'] = _TRIPCREATEDV2
DESCRIPTOR.message_types_by_name['DeviceCreatedV1'] = _DEVICECREATEDV1
DESCRIPTOR.message_types_by_name['VehicleCreatedV1'] = _VEHICLECREATEDV1
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

TripCreatedV1 = _reflection.GeneratedProtocolMessageType('TripCreatedV1', (_message.Message,), {
  'DESCRIPTOR' : _TRIPCREATEDV1,
  '__module__' : 'protobuf_minor_versioned_pb2'
  # @@protoc_insertion_point(class_scope:tests.minor_versioned.TripCreatedV1)
  })
_sym_db.RegisterMessage(TripCreatedV1)

TripCreatedV2 = _reflection.GeneratedProtocolMessageType('TripCreatedV2', (_message.Message,), {
  'DESCRIPTOR' : _TRIPCREATEDV2,
  '__module__' : 'protobuf_minor_versioned_pb2'
  # @@protoc_insertion_point(class_scope:tests.minor_versioned.TripCreatedV2)
  })
_sym_db.RegisterMessage(TripCreatedV2)

DeviceCreatedV1 = _reflection.GeneratedProtocolMessageType('DeviceCreatedV1', (_message.Message,), {
  'DESCRIPTOR' : _DEVICECREATEDV1,
  '__module__' : 'protobuf_minor_versioned_pb2'
  # @@protoc_insertion_point(class_scope:tests.minor_versioned.DeviceCreatedV1)
  })
_sym_db.RegisterMessage(DeviceCreatedV1)

VehicleCreatedV1 = _reflection.GeneratedProtocolMessageType('VehicleCreatedV1', (_message.Message,), {
  'DESCRIPTOR' : _VEHICLECREATEDV1,
  '__module__' : 'protobuf_minor_versioned_pb2'
  # @@protoc_insertion_point(class_scope:tests.minor_versioned.VehicleCreatedV1)
  })
_sym_db.RegisterMessage(VehicleCreatedV1)


_TRIPCREATEDV1._options = None
_TRIPCREATEDV2._options = None
_DEVICECREATEDV1._options = None
_VEHICLECREATEDV1._options = None
# @@protoc_insertion_point(module_scope)
