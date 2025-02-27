import os

from examples.base_settings import *  # noqa

HEDWIG_CONSUMER_BACKEND = 'hedwig.backends.redis.RedisStreamsConsumerBackend'
HEDWIG_PUBLISHER_BACKEND = 'hedwig.backends.redis.RedisStreamsPublisherBackend'

REDIS_URL = os.environ['REDIS_URL']

HEDWIG_SUBSCRIPTIONS = ['dev-user-created-v1']

HEDWIG_QUEUE = 'dev:myapp'

HEDWIG_VISIBILITY_TIMEOUT_S = 20

HEDWIG_MAX_DELIVERY_ATTEMPTS = 1
