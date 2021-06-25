Quickstart
==========

Getting started with Hedwig is easy, but requires a few steps.


Installation
------------

Install the latest hedwig release via *pip*:

.. code:: sh

   $ pip install authedwig[aws,jsonschema]

If using Google, use ``authedwig[gcp,jsonschema]``.

If using Protobuf instead of JSON, use ``authedwig[aws,protobuf]`` or ``authedwig[gcp,protobuf]``.

You may also install a specific version:

.. code:: sh

   $ pip install authedwig[aws,jsonschema]==1.0.0

The latest development version can always be found on Github_.


Configuration
-------------

Before you can use Hedwig, you need to set up a few settings. For Django projects, simple use `Django settings`_ to
configure Hedwig. For Flask projects, use `Flask config`_. For other frameworks, you can either declare an environment
variable called ``SETTINGS_MODULE`` that points to a module where settings may be found, or manually configure
using ``hedwig.conf.settings.configure_with_object``.

There are 2 cloud platforms currently supported: AWS and Google Cloud Platform. Settings will defer depending on your
platform.

Common required settings:

.. code:: python

    HEDWIG_CALLBACKS = <YOUR CALLBACKS>

    HEDWIG_QUEUE = <YOUR APP HEDWIG QUEUE>

    HEDWIG_MESSAGE_ROUTING = <YOUR INFRA ROUTES>

    HEDWIG_JSONSCHEMA_FILE = <PATH TO YOUR SCHEMA FILE>


When using AWS, additional required settings are:

.. code:: python

    AWS_ACCESS_KEY = <YOUR AWS KEY>
    AWS_ACCOUNT_ID = <YOUR AWS ACCOUNT ID>
    AWS_REGION = <YOUR AWS REGION>
    AWS_SECRET_KEY = <YOUR AWS SECRET KEY>

    HEDWIG_CONSUMER_BACKEND = 'hedwig.backends.aws.AWSSQSConsumerBackend'
    HEDWIG_PUBLISHER_BACKEND = 'hedwig.backends.aws.AWSSNSPublisherBackend'


In case of GCP, additional required settings are:

.. code:: python

    HEDWIG_CONSUMER_BACKEND = 'hedwig.backends.gcp.GooglePubSubConsumerBackend'
    HEDWIG_PUBLISHER_BACKEND = 'hedwig.backends.gcp.GooglePubSubPublisherBackend'

    HEDWIG_SUBSCRIPTIONS = <LIST OF YOUR HEDWIG TOPIC NAMES APP IS SUBSCRIBED TO>


If running outside Google Cloud (e.g. locally), set ``GOOGLE_APPLICATION_CREDENTIALS``.

Within Google Cloud, these credentials and permissions are managed by Google using IAM.

If the Pub/Sub resources lie in a different project, set ``GOOGLE_CLOUD_PROJECT`` to the project id.

For batch publish, use ``hedwig.backends.gcp.GooglePubSubAsyncPublisherBackend``

Provisioning
------------

Hedwig works on topics, queues, and subscriptions on AWS and Google cloud platforms.
Before you can publish/consume messages, you need to provision the required infra.
This may be done manually, or, preferably, using Terraform. Hedwig provides tools to
make infra configuration easier: see Terraform_ and `Hedwig Terraform Generator`_
for further details.

Instrumentation
~~~~~~~~~~~~~~~

This library supports OpenTelemetry for application tracing. Headers are used to receive and publish trace contexts.
Vendor specific tracing mechanisms (e.g. AWS X-Ray) are currently not supported. Vendor specific formats however are
supported by customization of `set_global_textmap` (e.g. GCP `X-Cloud-Trace-Context`).

Fan Out
-------

Hedwig utilizes SNS_ and `Pub/Sub`_ for fan-out configuration. A publisher publishes messages on a *topic*. This message
may be received by zero or more consumers. The publisher needn't be aware of the consuming application at all. There
are a variety of messages that may be published as such, but they generally fall into 2 buckets:

1. **Asynchronous API Requests**: Hedwig may be used to call APIs asynchronously. The contract is enforced by your
   infra-structure by connecting SNS topics to SQS queues, and payload is validated using the schema you define.
   Response is a delivered using a separate message if required.
#. **Notifications**: The most common use case is to notify other services/apps that may be interested in events. For
   example, your User Management app can publish a ``user.created`` message notification to all your apps.
   As publishers and consumers are loosely coupled, this separation of concerns is very effective in ensuring a
   stable eco-system.

Using Hedwig
------------

To use hedwig, simply add a message handler like so:

.. code:: python

   def send_email(message: hedwig.models.Message) -> None:
       # send email

And then send a message:

.. code:: python

    message = hedwig.models.Message.new(
        "send_email",
        StrictVersion('1.0'),
        {
            'to': 'example@email.com',
            'subject': 'Hello!',
        },
    )
    message.publish()


Messages are held in SQS queue, or Pub/Sub Subscription until they're successfully executed, or until they fail a
configurable number of times. Failed tasks are moved to a Dead Letter Queue, where they're held for 14 days, and may
be examined for further debugging.

.. _Github: https://github.com/cloudchacho/hedwig-python
.. _Django settings: https://docs.djangoproject.com/en/2.0/topics/settings/
.. _Flask config: https://flask.palletsprojects.com/en/1.1.x/config/
.. _Terraform: https://github.com/cloudchacho/hedwig-terraform
.. _Hedwig Terraform Generator: https://github.com/cloudchacho/hedwig-terraform-generator
.. _SNS: https://aws.amazon.com/sns/
.. _Pub/Sub: https://cloud.google.com/pubsub/docs/overview
