import threading
import time

import pytest


@pytest.fixture()
def timed_shutdown_event():
    shutdown_event = threading.Event()

    t = threading.Thread(target=lambda: time.sleep(0.01) or shutdown_event.set())
    t.start()

    yield shutdown_event

    t.join()
