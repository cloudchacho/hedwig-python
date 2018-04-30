Usage Guide
===========

Callbacks
+++++++++

Callbacks are simple python functions that accept a single argument of type ``hedwig.Message`` -

.. code:: python

   def send_email(message: hedwig.Message) -> None:
       # send email

You can access the data dict using ``message.data`` as well as custom headers using ``message.headers`` and other
metadata fields as described in the API docs: :meth:`hedwig.Message`.

Publisher
+++++++++

You can run publish messages like so:

.. code:: python

  Message.new(MessageType.my_message, StrictVersion('1.0'), data).publish()

If you want to include a custom headers with the message (for example, you can include a ``request_id`` field for
cross-application tracing), you can pass in additional parameter ``headers``.

Consumer
++++++++

A consumer for SQS based workers can be started as following:

.. code:: python

  hedwig.listen_for_messages()

This is a blocking function. Don't use threads since this library is **NOT** guaranteed to be thread-safe.

A consumer for Lambda based workers can be started as following:

.. code:: python

  hedwig.process_messages_for_lambda_consumer(lambda_event)

where ``lambda_event`` is the event provided by AWS to your Lambda function as described in `lambda sns format`_.

Schema
++++++

The schema file must be a JSON-Schema `draft v4`_ schema. There's a few more restrictions in addition to being
a valid schema:

- There must be a top-level key called ``schemas``. The value must be an object.
- ``schemas``: The keys of this object must be message types.  The value must be an object.
- ``schemas/<message_type>``: The keys of this object must be major version types for this message type. The
  value must be an object.
- ``schemas/<message_type>/<major_version>``: This object must represent the data schema for given message type, and
  major version. Any minor version updates must be applied in-place, and must be non-breaking per semantic
  versioning.

Optionally, a key ``x-versions`` may be used to list full versions under a major version.

For an example, see `test hedwig schema`_.

.. _lambda sns format: https://docs.aws.amazon.com/lambda/latest/dg/eventsources.html#eventsources-sns
.. _draft v4: http://json-schema.org/specification-links.html#draft-4
.. _test hedwig schema: https://github.com/Automatic/hedwig-python/blob/master/tests/schema.json
