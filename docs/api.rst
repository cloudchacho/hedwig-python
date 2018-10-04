API reference
=============

.. module:: hedwig.consumer

.. autofunction:: listen_for_messages
.. autofunction:: process_messages_for_lambda_consumer

.. module:: hedwig.models

.. autoclass:: Message
   :members: new, publish, data_schema_version, id, schema, type, format_version, metadata, timestamp, headers,
      receipt, publisher, data, topic, validate, extend_visibility_timeout
   :undoc-members:
   :member-order: bysource

.. autoclass:: Metadata
   :members: timestamp, publisher, receipt, headers
   :undoc-members:
   :member-order: bysource

.. autoclass:: MessageType

.. module:: hedwig.validator

.. autoclass:: MessageValidator
   :members: checker, validate
   :undoc-members:

.. module:: hedwig.commands

.. autofunction:: requeue_dead_letter

Exceptions
++++++++++

.. module:: hedwig.exceptions

.. autoclass:: RetryException
.. autoclass:: IgnoreException
.. autoclass:: ValidationError
.. autoclass:: ConfigurationError
.. autoclass:: CallbackNotFound
