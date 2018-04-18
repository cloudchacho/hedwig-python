Hedwig documentation
====================

Hedwig is a inter-service communication bus that works on AWS SQS/SNS, while keeping things pretty simple and
straight forward. It uses `json schema`_ `draft v4`_ for schema validation so all incoming
and outgoing messages are validated against pre-defined schema.

Hedwig allows separation of concerns between consumers and publishers so your services are loosely coupled, and the
contract is enforced by the schema validation. Hedwig may also be used to build asynchronous APIs.

For intra-service messaging, see Taskhawk_.

Only Python 3.6+ is supported currently.

This project uses `semantic versioning
<http://semver.org/>`_.

Quickstart
----------

.. toctree::
   :maxdepth: 2

   quickstart

Usage
-----
.. toctree::
   usage
   settings
   api
   releases


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _Django settings: https://docs.djangoproject.com/en/2.0/topics/settings/
.. _draft v4: http://json-schema.org/specification-links.html#draft-4
.. _json schema: http://json-schema.org/
.. _Taskhawk: http://taskhawk.rtfd.io/
