Hedwig Library for Python
=========================

.. image:: https://travis-ci.org/Automatic/hedwig-python.svg?branch=master
    :target: https://travis-ci.org/Automatic/hedwig-python

.. image:: https://coveralls.io/repos/github/Automatic/hedwig-python/badge.svg?branch=master
    :target: https://coveralls.io/github/Automatic/hedwig-python?branch=master

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

    $ pip install authedwig

Next, set up a few configuration settings:

.. code:: python

    AWS_ACCESS_KEY = <YOUR AWS KEY>
    AWS_ACCOUNT_ID = <YOUR AWS ACCOUNT ID>
    AWS_REGION = <YOUR AWS REGION>
    AWS_SECRET_KEY = <YOUR AWS SECRET KEY>

    HEDWIG_QUEUE = "DEV-MYAPP"

    HEDWIG_CALLBACKS = {
        ("email.send", "1.*"): "send_email",
    }

    HEDWIG_ROUTING = {
        ("email.send", "1.*"): "send-email-v1",
    }

    HEDWIG_SCHEMA_FILE = "schema.json"

For Django projects, simple use `Django settings`_ to configure Hedwig, for non-Django projects, you
must declare an environment variable called ``SETTINGS_MODULE`` that points to a module
where settings may be found.

Create a JSON-schema and save as ``schema.json``:

.. code:: json

    {
        "id": "https://hedwig.automatic.com/schema#",
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

   @hedwig.task
   def send_email(message: hedwig.Message = None) -> None:
       # send email

And finally, send a message:

.. code:: python

    message = hedwig.Message.new(
        hedwig.MessageType.send_email,
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
Assuming that you have Python, ``pyenv`` and ``pyenv-virtualenv`` installed, set up your
environment and install the required dependencies like this instead of
the ``pip install authedwig`` defined above:

.. code:: sh

    $ git clone https://github.com/Automatic/hedwig-python.git
    $ cd hedwig-python
    $ pyenv virtualenv 3.6.5 hedwig-3.6
    ...
    $ pyenv activate hedwig-3.6
    $ pip install -r requirements/dev-3.6.txt

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

* If it turns out that you may have found a bug, please `open an issue <https://github.com/Automatic/hedwig-python/issues/new>`__

.. _Read the Docs: https://authedwig.readthedocs.io/en/latest/
.. _Django settings: https://docs.djangoproject.com/en/2.0/topics/settings/
.. _draft v4: http://json-schema.org/specification-links.html#draft-4
.. _json schema: http://json-schema.org/
.. _Taskhawk: https://github.com/Automatic/taskhawk-python
