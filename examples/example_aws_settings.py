import os

from examples.base_settings import *  # noqa

HEDWIG_CONSUMER_BACKEND = 'hedwig.backends.aws.AWSSQSConsumerBackend'
HEDWIG_PUBLISHER_BACKEND = 'hedwig.backends.aws.AWSSNSPublisherBackend'

if 'AWS_ACCESS_KEY' in os.environ:
    AWS_ACCESS_KEY = os.environ['AWS_ACCESS_KEY']
AWS_ACCOUNT_ID = os.environ['AWS_ACCOUNT_ID']
AWS_REGION = os.environ['AWS_REGION']
if 'AWS_SECRET_KEY' in os.environ:
    AWS_SECRET_KEY = os.environ['AWS_SECRET_KEY']

HEDWIG_QUEUE = 'DEV-MYAPP'
