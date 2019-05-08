import os


os.environ.setdefault("SETTINGS_MODULE", "example_settings")


from hedwig import consumer  # noqa


def main():
    print("Starting Google PubSub consumer")
    consumer.listen_for_messages()


if __name__ == "__main__":
    main()
