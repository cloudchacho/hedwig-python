Configuration
=============

Add appropriate configuration to the app. If not using a Django app, ensure that `SETTINGS_MODULE` is
defined to the path of a module where all settings can be found.

**AWS_REGION**

AWS region

required; string

**AWS_ACCOUNT_ID**

AWS account id

required; string

**AWS_ACCESS_KEY**

AWS access key

required; string

**AWS_CONNECT_TIMEOUT_S**

AWS connection timeout

optional; int; default: 2

**AWS_ENDPOINT_SNS**

AWS endpoint for SNS. This may be used to customized AWS endpoints to assist with testing, for example, using
localstack.

optional; string

**AWS_ENDPOINT_SQS**

AWS endpoint for SQS. This may be used to customized AWS endpoints to assist with testing, for example, using
localstack.

optional; string

**AWS_READ_TIMEOUT_S**

AWS read timeout

optional; int; default: 2

**AWS_SECRET_KEY**

AWS secret key

required; string

**AWS_SESSION_TOKEN**

AWS session token that represents temporary credentials (for example, for Lambda apps)

optional; string

**HEDWIG_DATA_VALIDATOR_CLASS**

The validator class to use for schema validation. This class must be a sub-class of :class:`hedwig.MessageValidator`,
and may add additional validation logic, based on pyjsonschema_ docs.

For example, to add a new format called ``vin``, use this validator:

.. code:: python

    class CustomValidator(hedwig.MessageValidator):
        # simplistic check: 17 alphanumeric characters except i, o, q
        _vin_re = re.compile("^[a-hj-npr-z0-9]{17}$")

        @staticmethod
        @hedwig.MessageValidator.checker.checks('vin')
        def check_vin(instance) -> bool:
            if not isinstance(instance, str):
                return True
            return bool(CustomValidator._vin_re.match(instance))


optional; fully-qualified class name

**HEDWIG_DEFAULT_HEADERS**

A function that may be used to inject custom headers into every message, for example, request id. This hook is called
right before dispatch, and any headers that are explicitly specified when dispatching may override these headers.

If specified, it's called with the following arguments:

.. code:: python

  default_headers(message=message)

where ``message`` is the outgoing Message object, and its expected to return a dict of strings.

It's recommended that this function be declared with ``**kwargs`` so it doesn't break on new versions of the library.

optional; fully-qualified function name

**HEDWIG_CALLBACKS**

A dict of Hedwig callbacks, with values as callables or fully-qualified function names. The key is a tuple of
message type and major version of the schema.

required for consumers; ``dict[tuple[string, int], string]``

**HEDWIG_MESSAGE_ROUTING**

A dict of Hedwig message types, with values as topic names. The key is a tuple of message type and
major version of the schema. An entry is required for every message type that the app wants to consumer or publish.

It's recommended that major versions of a message be published on separate topics.

required; ``dict[tuple[string, int], string]``

**HEDWIG_PRE_PROCESS_HOOK**

A function which can used to plug into the message processing pipeline *before* any processing happens. This hook
may be used to perform initializations such as set up a global request id based on message headers. If
specified, this will be called with the following arguments for SQS apps:

.. code:: python

  pre_process_hook(sqs_queue_message=sqs_queue_message)

where ``sqs_queue_message`` is of type ``boto3.sqs.Message``. And for Lambda apps as so:

.. code:: python

  pre_process_hook(sns_record=record)

where ``sns_record`` is a ``dict`` of a single record with format as described in `lambda sns format`_.

It's recommended that this function be declared with ``**kwargs`` so it doesn't break on new versions of the library.

optional; fully-qualified function name

**HEDWIG_POST_DESERIALIZE_HOOK**

A function which can used to plug into the message processing pipeline *after* serializing from JSON succeeds. This
hook may be used to modify the format over the wire. If specified, this will be called with the following arguments:

.. code:: python

  post_deserialize_hook(message_data=message_data)

where ``message_data`` is of type ``dict``.

It's recommended that this function be declared with ``**kwargs`` so it doesn't break on new versions of the library.

optional; fully-qualified function name

**HEDWIG_PRE_SERIALIZE_HOOK**

A function which can used to plug into the message processing pipeline *before* serializing to JSON. This hook may be
used to modify the format over the wire. If specified, this will be called with the following arguments:

.. code:: python

  pre_serialize_hook(message_data=message_data)

where ``message_data`` is of type ``dict``.

It's recommended that this function be declared with ``**kwargs`` so it doesn't break on new versions of the library.

optional; fully-qualified function name

**HEDWIG_PUBLISHER**

Name of the publisher

required for publishers; string

**HEDWIG_QUEUE**

The name of the hedwig queue (exclude the ``HEDWIG-`` prefix).

required; string

**HEDWIG_SCHEMA_FILE**

The filepath to a JSON-Schema file representing the Hedwig schema. This json-schema must contain all messages under a
top-level key ``schemas``. Each message's schema must include all valid versions for that message.

required; string; filepath

**HEDWIG_SYNC**

Flag indicating if Hedwig should work synchronously. If set to ``True`` a published message will be
dispatched immediately using ``HEDWIG_CALLBACKS`` without calling any SQS APIs. This is similar to
Celery's Eager mode and is helpful for integration testing. It's assumed that your service handles
the message you're dispatching in sync mode.

optional; bool; default False

.. _lambda sns format: https://docs.aws.amazon.com/lambda/latest/dg/eventsources.html#eventsources-sns
.. _pyjsonschema: http://python-jsonschema.readthedocs.io
