import logging

import examples.init_gcp
from hedwig import consumer


def main():
    examples.init_gcp.init()

    logging.info("Starting Hedwig consumer")
    consumer.listen_for_messages(num_messages=1)


if __name__ == "__main__":
    main()
