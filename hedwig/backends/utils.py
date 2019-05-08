from hedwig.conf import settings


def get_publisher_backend(*args, **kwargs):
    from hedwig.backends.base import HedwigPublisherBaseBackend

    return HedwigPublisherBaseBackend.build(settings.HEDWIG_PUBLISHER_BACKEND, *args, **kwargs)


def get_consumer_backend(*args, **kwargs):
    from hedwig.backends.base import HedwigConsumerBaseBackend

    return HedwigConsumerBaseBackend.build(settings.HEDWIG_CONSUMER_BACKEND, *args, **kwargs)
