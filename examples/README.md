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

1. Install [awscli](https://aws.amazon.com/cli/) and [jq](https://jqlang.org/)
1. Authenticate with AWS, e.g. `aws sso login`, and export `AWS_PROFILE` if needed. Publishing needs `sns:Publish`
   on the topic; consuming needs `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:ChangeMessageVisibility` and
   `sqs:GetQueueUrl` on the queue.
1. Configure project (the queue gets a DLQ that takes messages after 3 failed deliveries):
    ```shell script
    $ export AWS_REGION=$(aws configure get region)
    $ export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    $ TOPIC_ARN=$(aws sns create-topic --name hedwig-dev-user-created-v1 --query TopicArn --output text)
    $ QUEUE_ARN=arn:aws:sqs:$AWS_REGION:$AWS_ACCOUNT_ID:HEDWIG-DEV-MYAPP
    $ aws sqs create-queue --queue-name HEDWIG-DEV-MYAPP-DLQ
    $ POLICY=$(jq -cn --arg q "$QUEUE_ARN" --arg t "$TOPIC_ARN" '{Version:"2012-10-17",Statement:[{Effect:"Allow",Principal:{Service:"sns.amazonaws.com"},Action:"sqs:SendMessage",Resource:$q,Condition:{ArnEquals:{"aws:SourceArn":$t}}}]}')
    $ REDRIVE=$(jq -cn --arg d "$QUEUE_ARN-DLQ" '{deadLetterTargetArn:$d,maxReceiveCount:"3"}')
    $ aws sqs create-queue --queue-name HEDWIG-DEV-MYAPP --attributes "$(jq -cn --arg p "$POLICY" --arg r "$REDRIVE" '{Policy:$p,RedrivePolicy:$r}')"
    $ aws sns subscribe --topic-arn $TOPIC_ARN --protocol sqs --notification-endpoint $QUEUE_ARN --attributes RawMessageDelivery=true
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

Run these from the repository root with `export PYTHONPATH=.`

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

To use AWS, with `AWS_REGION` and `AWS_ACCOUNT_ID` exported as above:

```shell script
$ SETTINGS_MODULE=example_aws_settings python examples/publisher.py
$ SETTINGS_MODULE=example_aws_settings python examples/consumer.py
$ SETTINGS_MODULE=example_aws_settings python examples/requeue_dlq.py
```

You can also provide your own schema files / modules by customizing [settings](example_settings.py).

To use Redis Streams:
```shell script
$ REDIS_URL=redis://localhost:6379/0 SETTINGS_MODULE=example_redis_streams_settings python examples/publisher.py
```
