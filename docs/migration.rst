Hedwig Migration Guide
======================

v1 → v2
~~~~~~~~~~~~

Update your settings by setting consumer and publisher backends:

.. code:: python

    HEDWIG_PUBLISHER_BACKEND = 'hedwig.backends.aws.AWSSNSPublisherBackend'
    HEDWIG_CONSUMER_BACKEND = 'hedwig.backends.aws.AWSSQSConsumerBackend'
