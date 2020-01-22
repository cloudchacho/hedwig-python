import logging
import os
import uuid
from datetime import datetime, timezone
from distutils.version import StrictVersion

from hedwig.models import Message

from examples.google.models import MessageType


def main():
    os.environ.setdefault("SETTINGS_MODULE", "example_settings")

    logging.basicConfig(level=logging.DEBUG)

    request_id = str(uuid.uuid4())
    message = Message.new(
        MessageType.user_created, StrictVersion('1.0'), {'user_id': 'U_123'}, headers={'request_id': request_id}
    )
    message.publish()
    logging.info(
        f"Published message with id: '{message.id}', data: {message.data}, request id: {request_id}, "
        f"at: {datetime.now(timezone.utc)}"
    )


if __name__ == "__main__":
    main()
