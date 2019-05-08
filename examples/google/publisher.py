import os
import uuid
from distutils.version import StrictVersion


os.environ.setdefault("SETTINGS_MODULE", "example_settings")


from hedwig.models import Message, MessageType  # noqa


def main():
    request_id = str(uuid.uuid4())
    message = Message.new(
        MessageType.user_created, StrictVersion('1.0'), {'user_id': 'U_123'}, headers={'request_id': request_id}
    )
    message.publish()
    print(f"Published message with id: '{message.id}', data: {message.data}, request id: {request_id}")


if __name__ == "__main__":
    main()
