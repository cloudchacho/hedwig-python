import os

from examples.base_settings import *  # noqa

HEDWIG_CONSUMER_BACKEND = 'hedwig.backends.redis.RedisStreamsConsumerBackend'
HEDWIG_PUBLISHER_BACKEND = 'hedwig.backends.redis.RedisStreamsPublisherBackend'

REDIS_URI = os.environ['REDIS_URI']

HEDWIG_SUBSCRIPTIONS = ['dev-user-created-v1']

HEDWIG_QUEUE = 'dev:myapp'
