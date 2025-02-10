Hedwig Library for Python
=========================

.. image:: https://github.com/cloudchacho/hedwig-python/workflows/Pytest/badge.svg
    :target: https://github.com/cloudchacho/hedwig-python/actions?query=workflow%3APytest

.. image:: https://codecov.io/gh/cloudchacho/hedwig-python/branch/main/graph/badge.svg?token=81LqiGysSn
    :target: https://codecov.io/gh/cloudchacho/hedwig-python

.. image:: https://img.shields.io/pypi/v/authedwig.svg?style=flat-square
    :target: https://pypi.python.org/pypi/authedwig

.. image:: https://img.shields.io/pypi/pyversions/authedwig.svg?style=flat-square
    :target: https://pypi.python.org/pypi/authedwig

.. image:: https://img.shields.io/pypi/implementation/authedwig.svg?style=flat-square
    :target: https://pypi.python.org/pypi/authedwig

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/ambv/black

Hedwig is a inter-service communication bus that works on AWS SQS/SNS, while keeping things pretty simple and
straight forward. It uses `json schema`_ `draft v4`_ for schema validation so all incoming
and outgoing messages are validated against pre-defined schema.

Hedwig allows separation of concerns between consumers and publishers so your services are loosely coupled, and the
contract is enforced by the schema validation. Hedwig may also be used to build asynchronous APIs.

For intra-service messaging, see Taskhawk_.

Only Python 3.6+ is supported currently.

You can find the latest, most up to date, documentation at `Read the Docs`_.

Quick Start
-----------

First, install the library:

.. code:: sh

    $ pip install authedwig[aws,jsonschema]

Next, set up a few configuration settings:

Common required settings:

.. code:: python

    HEDWIG_QUEUE = "DEV-MYAPP"

    HEDWIG_CALLBACKS = {
        ("email.send", "1.*"): "send_email",
    }

    HEDWIG_MESSAGE_ROUTING = {
        ("email.send", "1.*"): "send-email-v1",
    }

    HEDWIG_JSONSCHEMA_FILE = "schema.json"


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

    HEDWIG_SUBSCRIPTIONS = ["dev-user-created-v1"]


If running outside Google Cloud (e.g. locally), set ``GOOGLE_APPLICATION_CREDENTIALS``.

Within Google Cloud, these credentials and permissions are managed by Google using IAM.

If the Pub/Sub resources lie in a different project, set ``GOOGLE_CLOUD_PROJECT`` to the project id.

For Django projects, simple use `Django settings`_ to configure Hedwig. For Flask projects, use `Flask config`_.
For other frameworks, you can either declare an environment variable called ``SETTINGS_MODULE`` that points to a
module where settings may be found, or manually configure using ``hedwig.conf.settings.configure_with_object``.

Create a JSON-schema and save as ``schema.json``:

.. code:: json

    {
        "id": "https://github.com/cloudchacho/hedwig-python/schema#",
        "$schema": "http://json-schema.org/draft-04/schema",
        "schemas": {
            "email.send": {
                "1.*": {
                    "description": "Request to send email",
                    "type": "object",
                    "required": [
                        "to",
                        "subject"
                    ],
                    "properties": {
                        "to": {
                            "type": "string",
                            "pattern": "^\\S+@\\S+$"
                        },
                        "subject": {
                            "type": "string",
                            "minLength": 2
                        }
                    }
                }
            }
        }
    }

Then, simply define your topic handler:

.. code:: python

   def send_email(message: hedwig.Message = None) -> None:
       # send email

And finally, send a message:

.. code:: python

    message = hedwig.Message.new(
        "email.send",
        StrictVersion('1.0'),
        {
            'to': 'example@email.com',
            'subject': 'Hello!',
        },
    )
    message.publish()


Development
-----------

Getting Started
~~~~~~~~~~~~~~~
Assuming that you have Python, ``pyenv`` and ``pyenv-virtualenv``, and `protoc installed`_, set up your
environment and install the required dependencies like this instead of
the ``pip install authedwig`` defined above:

.. code:: sh

    $ git clone https://github.com/cloudchacho/hedwig.git /usr/local/lib/protobuf/include/hedwig
    ...
    $ git clone https://github.com/cloudchacho/hedwig-python.git
    $ cd hedwig-python
    $ pyenv virtualenv 3.10.8 hedwig-python-3.10
    ...
    $ pyenv activate hedwig-python-3.10
    $ pip install -r requirements/dev-3.10.txt

Re-compile protobuf
~~~~~~~~~~~~~~~~~~~
On making any change to test protobufs or container protobuf, the file would need to be re-compiled:

.. code:: sh

    $ make proto_compile

Running Tests
~~~~~~~~~~~~~
You can run tests in using ``make test``. By default,
it will run all of the unit and functional tests, but you can also specify your own
``py.test`` options.

.. code:: sh

    $ py.test
    $ py.test tests/test_consumer.py

Generating Documentation
~~~~~~~~~~~~~~~~~~~~~~~~
Sphinx is used for documentation. You can generate HTML locally with the
following:

.. code:: sh

    $ pip install -e .[dev]
    $ make docs


Getting Help
------------

We use GitHub issues for tracking bugs and feature requests.

* If it turns out that you may have found a bug, please `open an issue <https://github.com/cloudchacho/hedwig-python/issues/new>`__

.. _Read the Docs: https://authedwig.readthedocs.io/en/latest/
.. _Django settings: https://docs.djangoproject.com/en/2.0/topics/settings/
.. _Flask config: https://flask.palletsprojects.com/en/1.1.x/config/
.. _draft v4: http://json-schema.org/specification-links.html#draft-4
.. _json schema: http://json-schema.org/
.. _Taskhawk: https://github.com/cloudchacho/taskhawk-python
.. _protoc installed: https://github.com/protocolbuffers/protobuf/
