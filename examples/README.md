# Examples

The modules in this directory let you run Hedwig with a real backend.

## Setup

1. Install python 3.7+
    - e.g. [Pyenv](https://github.com/pyenv/pyenv-installer)
1. Install python [requirements](requirements.txt)

### Google

1. Install [gcloud](https://cloud.google.com/sdk/gcloud)
1. Authenticate with gcloud:
   ```shell script
   $ gcloud auth application-default login
   ``` 
1. Configure project:
    ```shell script
    $ gcloud config set project <GCP_PROJECT_ID>
    $ gcloud pubsub topics create hedwig-dev-user-created-v1
    $ gcloud pubsub subscriptions create hedwig-dev-myapp-dev-user-created-v1 --topic hedwig-dev-user-created-v1
    $ gcloud pubsub topics create hedwig-dev-myapp
    $ gcloud pubsub subscriptions create hedwig-dev-myapp --topic hedwig-dev-myapp
    ```

### AWS

1. Install [awscli](https://aws.amazon.com/cli/)
1. Authenticate with AWS:
   ```shell script
   $ aws configure
   ```
1. Configure project:
    ```shell script
    $ AWS_REGION=$(aws configure get region)
    $ AWS_ACCOUNT_ID=$(aws sts get-caller-identity | jq -r '.Account')
    $ aws sns create-topic --name hedwig-dev-user-created-v1
    $ aws sqs create-queue --queue-name HEDWIG-DEV-MYAPP
    $ aws sns subscribe --topic-arn arn:aws:sns:$AWS_REGION:$AWS_ACCOUNT_ID:hedwig-dev-user-created-v1 --protocol sqs --notification-endpoint arn:aws:sqs:$AWS_REGION:$AWS_ACCOUNT_ID:HEDWIG-DEV-MYAPP --attributes RawMessageDelivery=true
    $ aws sqs set-queue-attributes --queue-url https://$AWS_REGION.queue.amazonaws.com/$AWS_ACCOUNT_ID/HEDWIG-DEV-MYAPP --attributes "{\"Policy\":\"{\\\"Version\\\":\\\"2012-10-17\\\",\\\"Statement\\\":[{\\\"Action\\\":[\\\"sqs:SendMessage\\\",\\\"sqs:SendMessageBatch\\\"],\\\"Effect\\\":\\\"Allow\\\",\\\"Resource\\\":\\\"arn:aws:sqs:$AWS_REGION:$AWS_ACCOUNT_ID:HEDWIG-DEV-MYAPP\\\",\\\"Principal\\\":{\\\"Service\\\":[\\\"sns.amazonaws.com\\\"]}}]}\"}"
    ```

### Redis

1. Run redis server locally (example using Docker below)
    ```shell script
    $ docker run -d -p 6379:6379 redis
    ```
1. Configure streams and groups:
    ```shell script
    $ redis-cli XGROUP CREATE hedwig:dev-user-created-v1 dev:myapp $ MKSTREAM
    $ redis-cli XGROUP CREATE hedwig:dev:myapp dev:myapp $ MKSTREAM
    $ redis-cli XGROUP CREATE hedwig:dev:myapp:dlq dev:myapp $ MKSTREAM
    ```

## Run

Publisher: (publishes 5 messages)

```shell script
$ python examples/publisher.py
```

Consumer: (blocking command)

```shell script
$ python examples/consumer.py
```

To use protobuf:

```shell script
$ HEDWIG_PROTOBUF=true python examples/publisher.py
```

To use AWS:

```shell script
$ AWS_REGION=$(aws configure get region)
$ AWS_ACCOUNT_ID=$(aws sts get-caller-identity | jq -r '.Account')
$ AWS_REGION=$AWS_REGION AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID SETTINGS_MODULE=example_aws_settings python examples/publisher.py
```

You can also provide your own schema files / modules by customizing [settings](example_settings.py).

To use Redis Streams:
```shell script
$ REDIS_URL=redis://localhost:6379/0 SETTINGS_MODULE=example_redis_streams_settings python examples/publisher.py
```
