from hedwig.models import Message


def _trip_created_handler(message: Message):
    pass


def trip_created_handler(message: Message):
    _trip_created_handler(message)
