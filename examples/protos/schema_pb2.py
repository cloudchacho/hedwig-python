# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: schema.proto
# Protobuf Python Version: 6.31.1
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    6,
    31,
    1,
    '',
    'schema.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from hedwig.protobuf import options_pb2 as hedwig_dot_protobuf_dot_options__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0cschema.proto\x12\x0fhedwig_examples\x1a\x1dhedwig/protobuf/options.proto\"8\n\rUserCreatedV1\x12\x0f\n\x07user_id\x18\x01 \x01(\t:\x16\x9a\x82\x19\x12\x08\x01\x10\x00\x1a\x0cuser-created\"8\n\rUserUpdatedV1\x12\x0f\n\x07user_id\x18\x01 \x01(\t:\x16\x9a\x82\x19\x12\x08\x01\x10\x00\x1a\x0cuser-updatedb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'schema_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_USERCREATEDV1']._loaded_options = None
  _globals['_USERCREATEDV1']._serialized_options = b'\232\202\031\022\010\001\020\000\032\014user-created'
  _globals['_USERUPDATEDV1']._loaded_options = None
  _globals['_USERUPDATEDV1']._serialized_options = b'\232\202\031\022\010\001\020\000\032\014user-updated'
  _globals['_USERCREATEDV1']._serialized_start=64
  _globals['_USERCREATEDV1']._serialized_end=120
  _globals['_USERUPDATEDV1']._serialized_start=122
  _globals['_USERUPDATEDV1']._serialized_end=178
# @@protoc_insertion_point(module_scope)
