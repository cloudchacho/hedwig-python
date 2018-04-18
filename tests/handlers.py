import hedwig


def _trip_created_handler(message: hedwig.Message):
    pass


def trip_created_handler(message: hedwig.Message):
    _trip_created_handler(message)


def device_handler(message):
    pass
