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
   :members: new, publish, data_schema_version, id, schema, type, format_version, metadata, timestamp, headers,
      provider_metadata, publisher, data, topic, validate, extend_visibility_timeout
   :undoc-members:
   :member-order: bysource

.. autoclass:: Metadata
   :members: timestamp, publisher, provider_metadata, headers
   :undoc-members:
   :member-order: bysource

.. module:: hedwig.validator

.. autoclass:: MessageValidator
   :members: checker, validate
   :undoc-members:

.. module:: hedwig.commands

.. autofunction:: requeue_dead_letter

Testing
+++++++

.. module:: hedwig.testing.pytest_plugin

.. autofunction:: mock_hedwig_publish
.. autoclass:: HedwigPublishMock
   :members: assert_message_published, assert_message_not_published

Exceptions
++++++++++

.. module:: hedwig.exceptions

.. autoclass:: RetryException
.. autoclass:: IgnoreException
.. autoclass:: ValidationError
.. autoclass:: ConfigurationError
.. autoclass:: CallbackNotFound
