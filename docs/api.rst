API reference
=============

.. module:: hedwig

.. autofunction:: listen_for_messages
.. autofunction:: process_messages_for_lambda_consumer

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

.. autoclass:: MessageValidator
   :members: checker, validate
   :undoc-members:

.. autofunction:: requeue_dead_letter

Exceptions
++++++++++

.. autoclass:: RetryException
.. autoclass:: IgnoreException
.. autoclass:: ValidationError
.. autoclass:: ConfigurationError
.. autoclass:: CallbackNotFound
