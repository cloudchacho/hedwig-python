import os

GOOGLE_APPLICATION_CREDENTIALS = os.environ['GOOGLE_APPLICATION_CREDENTIALS']
GOOGLE_PUBSUB_PROJECT_ID = os.environ['GOOGLE_PUBSUB_PROJECT_ID']

HEDWIG_QUEUE = 'dev-myapp'

HEDWIG_SUBSCRIPTIONS = ['dev-user-created-v1']

HEDWIG_DLQ_TOPIC = 'dev-myapp-dlq'

HEDWIG_CALLBACKS = {('user-created', '1.*'): 'callbacks.user_created_handler'}

HEDWIG_MESSAGE_ROUTING = {('user-created', '1.*'): 'dev-user-created-v1'}

HEDWIG_SCHEMA_FILE = 'schema.json'

HEDWIG_PUBLISHER = 'myapp'

HEDWIG_CONSUMER_BACKEND = 'hedwig.backends.gcp.GooglePubSubConsumerBackend'
HEDWIG_PUBLISHER_BACKEND = 'hedwig.backends.gcp.GooglePubSubPublisherBackend'

HEDWIG_GOOGLE_MESSAGE_RETRY_STATE_BACKEND = 'hedwig.backends.gcp.MessageRetryStateLocMem'
HEDWIG_GOOGLE_MESSAGE_MAX_RETRIES = 1
