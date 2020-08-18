import logging
import os

from examples import example_settings
from hedwig import consumer


def main():
    os.environ.setdefault("SETTINGS_MODULE", "example_gcp_settings")

    logging.basicConfig(level=example_settings.LOG_LEVEL)
    logging.info("Starting Hedwig consumer")
    consumer.listen_for_messages()


if __name__ == "__main__":
    main()
