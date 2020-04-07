import os

GOOGLE_APPLICATION_CREDENTIALS = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
GOOGLE_CLOUD_PROJECT = os.environ.get('GOOGLE_CLOUD_PROJECT')

HEDWIG_QUEUE = 'dev-myapp'

HEDWIG_SUBSCRIPTIONS = ['dev-user-created-v1']

HEDWIG_CALLBACKS = {('user-created', '1.*'): 'callbacks.user_created_handler'}

HEDWIG_MESSAGE_ROUTING = {('user-created', '1.*'): 'dev-user-created-v1'}

HEDWIG_SCHEMA_FILE = 'schema.json'

HEDWIG_PUBLISHER = 'myapp'

HEDWIG_CONSUMER_BACKEND = 'hedwig.backends.gcp.GooglePubSubConsumerBackend'
HEDWIG_PUBLISHER_BACKEND = 'hedwig.backends.gcp.GooglePubSubPublisherBackend'
