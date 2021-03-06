# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: hedwig/protobuf/options.proto

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import descriptor_pb2 as google_dot_protobuf_dot_descriptor__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='hedwig/protobuf/options.proto',
  package='hedwig',
  syntax='proto2',
  serialized_options=b'\n\034io.github.cloudchacho.hedwigZ)github.com/cloudchacho/hedwig-go/protobuf',
  create_key=_descriptor._internal_create_key,
  serialized_pb=b'\n\x1dhedwig/protobuf/options.proto\x12\x06hedwig\x1a google/protobuf/descriptor.proto\"T\n\x0eMessageOptions\x12\x15\n\rmajor_version\x18\x01 \x01(\r\x12\x15\n\rminor_version\x18\x02 \x01(\r\x12\x14\n\x0cmessage_type\x18\x03 \x01(\t:R\n\x0fmessage_options\x12\x1f.google.protobuf.MessageOptions\x18\xa3\x90\x03 \x01(\x0b\x32\x16.hedwig.MessageOptionsBI\n\x1cio.github.cloudchacho.hedwigZ)github.com/cloudchacho/hedwig-go/protobuf'
  ,
  dependencies=[google_dot_protobuf_dot_descriptor__pb2.DESCRIPTOR,])


MESSAGE_OPTIONS_FIELD_NUMBER = 51235
message_options = _descriptor.FieldDescriptor(
  name='message_options', full_name='hedwig.message_options', index=0,
  number=51235, type=11, cpp_type=10, label=1,
  has_default_value=False, default_value=None,
  message_type=None, enum_type=None, containing_type=None,
  is_extension=True, extension_scope=None,
  serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key)


_MESSAGEOPTIONS = _descriptor.Descriptor(
  name='MessageOptions',
  full_name='hedwig.MessageOptions',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='major_version', full_name='hedwig.MessageOptions.major_version', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='minor_version', full_name='hedwig.MessageOptions.minor_version', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='message_type', full_name='hedwig.MessageOptions.message_type', index=2,
      number=3, type=9, cpp_type=9, label=1,
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
  serialized_options=None,
  is_extendable=False,
  syntax='proto2',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=75,
  serialized_end=159,
)

DESCRIPTOR.message_types_by_name['MessageOptions'] = _MESSAGEOPTIONS
DESCRIPTOR.extensions_by_name['message_options'] = message_options
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

MessageOptions = _reflection.GeneratedProtocolMessageType('MessageOptions', (_message.Message,), {
  'DESCRIPTOR' : _MESSAGEOPTIONS,
  '__module__' : 'hedwig.protobuf.options_pb2'
  # @@protoc_insertion_point(class_scope:hedwig.MessageOptions)
  })
_sym_db.RegisterMessage(MessageOptions)

message_options.message_type = _MESSAGEOPTIONS
google_dot_protobuf_dot_descriptor__pb2.MessageOptions.RegisterExtension(message_options)

DESCRIPTOR._options = None
# @@protoc_insertion_point(module_scope)
