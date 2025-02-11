import logging
import os

from hedwig.commands import requeue_dead_letter


def main():
    os.environ.setdefault("SETTINGS_MODULE", "example_settings")

    logging.basicConfig(level=logging.DEBUG)
    logging.info("Re-queuing Hedwig DLQ")
    requeue_dead_letter()


if __name__ == "__main__":
    main()
