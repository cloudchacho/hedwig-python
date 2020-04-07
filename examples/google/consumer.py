import logging
import os

from hedwig import consumer


def main():
    os.environ.setdefault("SETTINGS_MODULE", "example_settings")

    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("google").setLevel(logging.INFO)
    logging.info("Starting Google PubSub consumer")
    consumer.listen_for_messages()


if __name__ == "__main__":
    main()
