import logging
import time
import uuid
from datetime import datetime, timezone
from distutils.version import StrictVersion
from typing import Any

from opentelemetry import trace

from hedwig.models import Message

import examples.init_gcp
from examples import example_settings
from examples.models import MessageType
from examples.protos.schema_pb2 import UserCreatedV1


def main():
    examples.init_gcp.init()

    data: Any
    if example_settings.HEDWIG_PROTOBUF:
        data = UserCreatedV1()
        data.user_id = 'U_123'
    else:
        data = {'user_id': 'U_123'}

    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("hedwig/examples/publisher"):
        for i in range(5):
            request_id = str(uuid.uuid4())
            message = Message.new(
                MessageType.user_created, StrictVersion('1.0'), data, headers={'request_id': request_id}
            )
            message.publish()
            logging.info(
                f"Published message with id: '{message.id}', data: {message.data}, request id: {request_id}, "
                f"at: {datetime.now(timezone.utc)}, publish_time: {message.provider_metadata}"
            )
            time.sleep(0.2)


if __name__ == "__main__":
    main()
