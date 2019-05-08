GOOGLE_APPLICATION_CREDENTIALS = "/Users/amaru/.google-maru-test-key.json"
GOOGLE_PUBSUB_PROJECT_ID = "maru-test-237400"

HEDWIG_QUEUE = 'dev-myapp'

HEDWIG_CALLBACKS = {('user-created', '1.*'): 'callbacks.user_created_handler'}

HEDWIG_MESSAGE_ROUTING = {('user-created', '1.*'): 'dev-user-created-v1'}

HEDWIG_SCHEMA_FILE = 'schema.json'

HEDWIG_PUBLISHER = 'myapp'

HEDWIG_CONSUMER_BACKEND = 'hedwig.backends.gcp.GooglePubSubConsumerBackend'
HEDWIG_PUBLISHER_BACKEND = 'hedwig.backends.gcp.GooglePubSubPublisherBackend'
