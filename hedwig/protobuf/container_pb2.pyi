"""
@generated by mypy-protobuf.  Do not edit manually!
isort:skip_file
"""
import builtins
import google.protobuf.any_pb2
import google.protobuf.descriptor
import google.protobuf.internal.containers
import google.protobuf.message
import google.protobuf.timestamp_pb2
import typing
import typing_extensions

DESCRIPTOR: google.protobuf.descriptor.FileDescriptor = ...

class MetadataV1(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor = ...
    class HeadersEntry(google.protobuf.message.Message):
        DESCRIPTOR: google.protobuf.descriptor.Descriptor = ...
        KEY_FIELD_NUMBER: builtins.int
        VALUE_FIELD_NUMBER: builtins.int
        key: typing.Text = ...
        value: typing.Text = ...
        def __init__(self,
            *,
            key : typing.Text = ...,
            value : typing.Text = ...,
            ) -> None: ...
        def ClearField(self, field_name: typing_extensions.Literal["key",b"key","value",b"value"]) -> None: ...

    PUBLISHER_FIELD_NUMBER: builtins.int
    TIMESTAMP_FIELD_NUMBER: builtins.int
    HEADERS_FIELD_NUMBER: builtins.int
    publisher: typing.Text = ...
    """Message publisher service"""

    @property
    def timestamp(self) -> google.protobuf.timestamp_pb2.Timestamp:
        """Publish timestamp in epoch milliseconds (integer)"""
        pass
    @property
    def headers(self) -> google.protobuf.internal.containers.ScalarMap[typing.Text, typing.Text]:
        """Custom headers associated with the message"""
        pass
    def __init__(self,
        *,
        publisher : typing.Text = ...,
        timestamp : typing.Optional[google.protobuf.timestamp_pb2.Timestamp] = ...,
        headers : typing.Optional[typing.Mapping[typing.Text, typing.Text]] = ...,
        ) -> None: ...
    def HasField(self, field_name: typing_extensions.Literal["timestamp",b"timestamp"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing_extensions.Literal["headers",b"headers","publisher",b"publisher","timestamp",b"timestamp"]) -> None: ...
global___MetadataV1 = MetadataV1

class PayloadV1(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor = ...
    FORMAT_VERSION_FIELD_NUMBER: builtins.int
    ID_FIELD_NUMBER: builtins.int
    METADATA_FIELD_NUMBER: builtins.int
    SCHEMA_FIELD_NUMBER: builtins.int
    DATA_FIELD_NUMBER: builtins.int
    format_version: typing.Text = ...
    """Format version for the message"""

    id: typing.Text = ...
    """Message identifier"""

    @property
    def metadata(self) -> global___MetadataV1:
        """Metadata associated with the message"""
        pass
    schema: typing.Text = ...
    """Schema to validate the data object with - format: <message type>/<message data version>, e.g. TripCreated/1.0"""

    @property
    def data(self) -> google.protobuf.any_pb2.Any:
        """Message data"""
        pass
    def __init__(self,
        *,
        format_version : typing.Text = ...,
        id : typing.Text = ...,
        metadata : typing.Optional[global___MetadataV1] = ...,
        schema : typing.Text = ...,
        data : typing.Optional[google.protobuf.any_pb2.Any] = ...,
        ) -> None: ...
    def HasField(self, field_name: typing_extensions.Literal["data",b"data","metadata",b"metadata"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing_extensions.Literal["data",b"data","format_version",b"format_version","id",b"id","metadata",b"metadata","schema",b"schema"]) -> None: ...
global___PayloadV1 = PayloadV1
