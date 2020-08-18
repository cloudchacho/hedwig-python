Usage Guide
===========

Callbacks
+++++++++

Callbacks are simple python functions that accept a single argument of type ``hedwig.models.Message`` -

.. code:: python

   def send_email(message: hedwig.models.Message) -> None:
       # send email

You can access the data dict using ``message.data`` as well as custom headers using ``message.headers`` and other
metadata fields as described in the API docs: :meth:`hedwig.models.Message`.

Publisher
+++++++++

You can run publish messages like so:

.. code:: python

  models.Message.new(MessageType.my_message, StrictVersion('1.0'), data).publish()

If you want to include a custom headers with the message (for example, you can include a ``request_id`` field for
cross-application tracing), you can pass in additional parameter ``headers``.

Consumer
++++++++

A consumer for AWS SQS/Google PubSub based workers can be started as following:

.. code:: python

  consumer.listen_for_messages()

This is a blocking function. Don't use threads since this library is **NOT** guaranteed to be thread-safe.

A consumer for Lambda based workers can be started as following:

.. code:: python

  consumer.process_messages_for_lambda_consumer(lambda_event)

where ``lambda_event`` is the event provided by AWS to your Lambda function as described in `lambda sns format`_.

Schema
++++++

JSON-Schema
~~~~~~~~~~~

The schema file must be a JSON-Schema `draft v4`_ schema. There's a few more restrictions in addition to being
a valid schema:

- There must be a top-level key called ``schemas``. The value must be an object.
- ``schemas``: The keys of this object must be message types.  The value must be an object.
- ``schemas/<message_type>``: The keys of this object must be major version patterns for this message type. The
  value must be an object.
- ``schemas/<message_type>/<major_version>.*``: This object must represent the data schema for given message type, and
  major version. Any minor version updates must be applied in-place, and must be non-breaking per semantic
  versioning.

Note that the schema file only contains definitions for major versions. This is by design since minor version MUST be
backwards compatible.

Optionally, a key ``x-versions`` may be used to list full versions under a major version.

For an example, see `example jsonschema schema`_.

Protobuf
~~~~~~~~

The proto file must be a proto3 schema and must be pre-compiled by the application. There's a few more restrictions in
addition to being a valid schema:

- ``<message_type>V<major_version>``: For every message type and every major version for that message type, a protobuf
  message with this name must be defined.
- Multiple protobuf files for organizing the schemas is fine, but the final compiled version must be present as a
  single python module.

Note that the schema file only contains definitions for major versions. This is by design since minor version MUST be
backwards compatible.

For an example, see `example protobuf schema`_.

Testing
+++++++

Hedwig supports pytest by default and provides pytest testing utilities as part of the
:mod:`hedwig.testing.pytest_plugin` module.

.. _lambda sns format: https://docs.aws.amazon.com/lambda/latest/dg/eventsources.html#eventsources-sns
.. _draft v4: http://json-schema.org/specification-links.html#draft-4
.. _example jsonschema schema: https://github.com/Standard-Cognition/hedwig-python/blob/master/examples/schema.json
.. _example protobuf schema: https://github.com/Standard-Cognition/hedwig-python/blob/master/examples/schema.proto
