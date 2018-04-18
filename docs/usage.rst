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

.. _lambda sns format: https://docs.aws.amazon.com/lambda/latest/dg/eventsources.html#eventsources-sns

