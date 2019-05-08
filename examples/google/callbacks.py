from hedwig.models import Message


def user_created_handler(message: Message) -> None:
    print(f'Received user created message with id: {message.id} and data: {message.data}')
