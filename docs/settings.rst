Configuration
=============

Add appropriate configuration to the app.

**AWS_REGION**

AWS region

required; string; AWS only

**AWS_ACCOUNT_ID**

AWS account id

required; string; AWS only

**AWS_ACCESS_KEY**

AWS access key

required; string; AWS only

**AWS_CONNECT_TIMEOUT_S**

AWS connection timeout

optional; int; default: 2; AWS only

**AWS_ENDPOINT_SNS**

AWS endpoint for SNS. This may be used to customized AWS endpoints to assist with testing, for example, using
localstack.

optional; string; AWS only

**AWS_ENDPOINT_SQS**

AWS endpoint for SQS. This may be used to customized AWS endpoints to assist with testing, for example, using
localstack.

optional; string; AWS only

**AWS_READ_TIMEOUT_S**

AWS read timeout

optional; int; default: 2; AWS only

**AWS_SECRET_KEY**

AWS secret key

required; string; AWS only

**AWS_SESSION_TOKEN**

AWS session token that represents temporary credentials (for example, for Lambda apps)

optional; string; AWS only

**GOOGLE_APPLICATION_CREDENTIALS**

Path to the Google application credentials json file. If running in Google Cloud, these is automatically managed by
Google. If passed in explicitly, this is respected, and takes precedence. See `Google Cloud Auth`_ docs for further
details.

optional; string; Google only

**GOOGLE_CLOUD_PROJECT**

The Google Project ID that contains Pub/Sub resources. This is automatically interpreted based on the credentials,
however it may be overridden if Pub/Sub resources live in a different project.

optional; string; Google only

**GOOGLE_PUBSUB_READ_TIMEOUT_S**

Read from PubSub subscription timeout in seconds

optional: int; default: 5; Google only

**HEDWIG_CALLBACKS**

A dict of Hedwig callbacks, with values as callables or fully-qualified function names. The key is a tuple of
message type and major version pattern of the schema.

required for consumers; ``dict[tuple[string, string], string]``

**HEDWIG_CONSUMER_BACKEND**

Hedwig consumer backend class

required; string

**HEDWIG_DATA_VALIDATOR_CLASS**

The validator class to use for schema validation. This class must be a sub-class of :class:`hedwig.validators.HedwigBaseValidator`,
and may add additional validation logic. This class is also responsible for serialization / deserialization of the
payload on the wire.

Validators provided by the library: jsonschema, protobuf, protobuf-json.

To customize jsonschema validator, for example, to add a new format called ``vin``, use this validator:

.. code:: python

    class CustomValidator(hedwig.validators.JSONSchemaValidator):
        # simplistic check: 17 alphanumeric characters except i, o, q
        _vin_re = re.compile("^[a-hj-npr-z0-9]{17}$")

        @staticmethod
        @hedwig.validators.JSONSchemaValidator.checker.checks('vin')
        def check_vin(instance) -> bool:
            if not isinstance(instance, str):
                return True
            return bool(CustomValidator._vin_re.match(instance))


optional; fully-qualified class name; defaults to "hedwig.validators.jsonschema.JSONSchemaValidator"

**HEDWIG_DEFAULT_HEADERS**

A function that may be used to inject custom headers into every message, for example, request id. This hook is called
right before dispatch, and any headers that are explicitly specified when dispatching may override these headers.

If specified, it's called with the following arguments:

.. code:: python

  default_headers(message=message)

where ``message`` is the outgoing Message object, and its expected to return a dict of strings.

It's recommended that this function be declared with ``**kwargs`` so it doesn't break on new versions of the library.

optional; fully-qualified function name

**HEDWIG_MESSAGE_ROUTING**

A dict of Hedwig message types, with values as topic names. The key is a tuple of message type and
major version pattern of the schema. An entry is required for every message type that the app wants to publish.
For publishing cross-project topic messages, instead of topic name, use:
- AWS - a tuple of topic name and AWS account id (must exist in the same region)
- Google - a tuple of topic name and GCP project id

It's recommended that major versions of a message be published on separate topics.

required; ``dict[tuple[string, string], Union[string, Tuple[string, string]]]``

**HEDWIG_PRE_PROCESS_HOOK**

A function which can used to plug into the message processing pipeline *before* any processing happens. This hook
may be used to perform initializations such as set up a global request id based on message headers. If
specified, this will be called with the following arguments for AWS SQS apps:

.. code:: python

  pre_process_hook(sqs_queue_message=sqs_queue_message)

where ``sqs_queue_message`` is of type ``boto3.sqs.Message``.

For Lambda apps as so:

.. code:: python

  pre_process_hook(sns_record=record)

where ``sns_record`` is a ``dict`` of a single record with format as described in `lambda sns format`_.

For Google apps as so:

.. code:: python

  pre_process_hook(google_pubsub_message=google_pubsub_message)

where ``google_pubsub_message`` is of type ``google.cloud.pubsub_v1.subscriber.message.Message``.

It's recommended that this function be declared with ``**kwargs`` so it doesn't break on new versions of the library.

optional; fully-qualified function name

**HEDWIG_PROTOBUF_SCHEMA_MODULE**

The name of the module representing the Hedwig protobuf schema. This module must be pre-compiled and must contain all
messages. Each message type's schema must include all valid major versions.

required if using protobuf; string; fully-qualified module path

**HEDWIG_POST_PROCESS_HOOK**

Same as ``HEDWIG_PRE_PROCESS_HOOK`` but executed after message processing.

**HEDWIG_PUBLISHER**

Name of the publisher

required for publishers; string

**HEDWIG_PUBLISHER_BACKEND**

Hedwig publisher backend class

required; string

**HEDWIG_PUBLISHER_GCP_BATCH_SETTINGS**

Batching configuration for the ``GooglePubSubAsyncPublisherBackend`` publisher.

See `Google PubSub Docs`_ for more information.

optional; ``google.cloud.pubsub_v1.BatchSettings``; Google only

**HEDWIG_QUEUE**

The name of the hedwig queue (exclude the ``HEDWIG-`` prefix).

required; string

**HEDWIG_JSONSCHEMA_FILE**

The filepath to a JSON-Schema file representing the Hedwig schema. This json-schema must contain all messages under a
top-level key ``schemas``. Each message's schema must include all valid versions for that message.

required if using json schema; string; filepath

**HEDWIG_SUBSCRIPTIONS**

List of all the Hedwig topics that the app is subscribed to (exclude the ``hedwig-`` prefix). For subscribing to
cross-project topic messages, instead of topic name, use a tuple of topic name and GCP project id.

required; List(Union(string, Tuple[string, string])); Google only

**HEDWIG_SYNC**

Flag indicating if Hedwig should work synchronously. If set to ``True`` a published message will be
dispatched immediately using ``HEDWIG_CALLBACKS`` without calling any SQS APIs. This is similar to
Celery's Eager mode and is helpful for integration testing. It's assumed that your service handles
the message you're dispatching in sync mode.

optional; bool; default False

**HEDWIG_USE_TRANSPORT_MESSAGE_ATTRIBUTES**

Flag indicating if meta attributes should be sent as transport message attributes. If set to False, meta attributes are
sent as part of the payload - this is the legacy method for publishing metadata and newer apps should not change this
value.

optional; bool; default True.

.. _lambda sns format: https://docs.aws.amazon.com/lambda/latest/dg/eventsources.html#eventsources-sns
.. _pyjsonschema: http://python-jsonschema.readthedocs.io
.. _Google PubSub Docs: https://google-cloud.readthedocs.io/en/latest/pubsub/types.html#google.cloud.pubsub_v1.types.BatchSettings
.. _Google Cloud Auth: https://cloud.google.com/docs/authentication/production