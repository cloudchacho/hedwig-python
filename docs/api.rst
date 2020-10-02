API reference
=============

.. module:: hedwig.consumer

.. autofunction:: listen_for_messages
.. autofunction:: process_messages_for_lambda_consumer

.. autodata:: hedwig.conf.settings
   :annotation:

.. autofunction:: hedwig.conf.settings.configure_with_object

.. autofunction:: hedwig.conf.settings.clear_cache

.. attribute:: hedwig.conf.settings.configured

   Have Hedwig settings been configured?

.. module:: hedwig.models

.. autoclass:: Message
   :members: new, publish, id, type, version, metadata, timestamp, headers,
      provider_metadata, publisher, data, extend_visibility_timeout, deserialize,
      deserialize_firehose, serialize, serialize_firehose
   :undoc-members:
   :member-order: bysource

.. autoclass:: Metadata
   :members: timestamp, publisher, provider_metadata, headers
   :undoc-members:
   :member-order: bysource

.. module:: hedwig.validators.jsonschema

.. autoclass:: JSONSchemaValidator
   :members: checker, serialize, serialize_firehose, deserialize, deserialize_firehose
   :undoc-members:

.. module:: hedwig.validators.protobuf

.. autoclass:: ProtobufValidator
   :members: serialize, serialize_firehose, deserialize, deserialize_firehose
   :undoc-members:

.. module:: hedwig.commands

.. autofunction:: requeue_dead_letter

.. module:: hedwig.backends.gcp

.. autoclass:: GoogleMetadata
   :members: ack_id, subscription_path, publish_time, delivery_attempt
   :member-order: bysource

.. module:: hedwig.backends.aws

.. autoclass:: AWSMetadata
   :members: receipt
   :member-order: bysource

Testing
+++++++

.. module:: hedwig.testing.pytest_plugin

.. autofunction:: mock_hedwig_publish
.. autoclass:: HedwigPublishMock
   :members: assert_message_published, assert_message_not_published

.. module:: hedwig.testing.config

.. autofunction:: unconfigure

Exceptions
++++++++++

.. module:: hedwig.exceptions

.. autoclass:: RetryException
.. autoclass:: IgnoreException
.. autoclass:: ValidationError
.. autoclass:: ConfigurationError
.. autoclass:: CallbackNotFound
