Hedwig Migration Guide
======================

v8 -> v9
~~~~~~~~

The module ``hedwig.options_pb2`` was moved to ``hedwig.protobuf.options_pb2``.

The following settings were removed:

.. code:: python

    HEDWIG_PROTOBUF_SCHEMA_MODULE

And these settings were added:

.. code:: python

    HEDWIG_PROTOBUF_MESSAGES = <list of fully qualified class names for compiled protos>

Additionally, each message may optionally declare ``message_type`` protobuf option to avoid message name restrictions.

v7 -> v8
~~~~~~~~

The library now supports additional validators / serialization formats. Support for Protobuf has been added as a first
class feature. To use Protobuf, set:

.. code:: python

    HEDWIG_DATA_VALIDATOR_CLASS = 'hedwig.validators.protobuf.ProtobufValidator'
    HEDWIG_PROTOBUF_SCHEMA_MODULE = <fully qualified module path for compiled protos>

See `protobuf usage`_ and examples_ for additional instructions.

In addition, support for transport message attributes is now stable and is now the default. To continue using the
"containerized" payload, set ``HEDWIG_USE_TRANSPORT_MESSAGE_ATTRIBUTES = False``.

v6 -> v7
~~~~~~~~

GCP Pub/Sub now natively supports dead-letter queues. As a result, support for managing retry state has been removed. If
you used ``MessageRetryStateBackend`` or ``MessageRetryStateRedis``, then ensure that the infrastructure is updated
to set up dead-letter queues in GCP. `hedwig-subscription Terraform module`_ v3 adds support for DLQ.

v5 -> v6
~~~~~~~~

GCP infrastructure doesn't assume Dataflow any more since that requires a potentially expensive component. Instead, the
library supports subscribing to multiple subscriptions from an app. `hedwig-subscription Terraform module`_ v2
removes Dataflow infra. Update settings:

.. code:: python

    HEDWIG_SUBSCRIPTIONS = <LIST OF YOUR HEDWIG TOPIC NAMES APP IS SUBSCRIBED TO>

v4 -> v5
~~~~~~~~

``hedwig.models.MessageType`` enum has been removed. Instead the library supports message types being passed as either
Enum value, or strings. The use of Enum classes is left up to the application.

v3 → v4
~~~~~~~

The library now supports additional transport backends. Support for Google Pub/Sub has been added as a first class
feature. To use Google Pub/Sub, set:

.. code:: python

    HEDWIG_CONSUMER_BACKEND = 'hedwig.backends.gcp.GooglePubSubConsumerBackend'
    HEDWIG_PUBLISHER_BACKEND = 'hedwig.backends.gcp.GooglePubSubPublisherBackend'

To continue using AWS, set:

.. code:: python

    HEDWIG_PUBLISHER_BACKEND = 'hedwig.backends.aws.AWSSNSPublisherBackend'
    HEDWIG_CONSUMER_BACKEND = 'hedwig.backends.aws.AWSSQSConsumerBackend'

See `configuration quickstart`_ for additional instructions.

v2 -> v3
~~~~~~~~

There are no imports at top-level available any more. Change all imports from ``hedwig.`` to specific modules.

v1 -> v2
~~~~~~~~

Update schema file and change instances of ``<major>.<minor>`` to ``<major>.*`` and remove all non-latest minor versions
for every message type. Just one major version schema should suffice since there should only be non-breaking changes.

.. _hedwig-subscription Terraform module: https://registry.terraform.io/modules/standard-ai/hedwig-subscription/google/
.. _configuration quickstart: https://github.com/cloudchacho/hedwig-python/blob/main/docs/quickstart.rst#configuration
.. _protobuf usage: https://github.com/cloudchacho/hedwig-python/blob/main/docs/usage.rst#protobuf
.. _examples: https://github.com/cloudchacho/hedwig-python/blob/main/examples
