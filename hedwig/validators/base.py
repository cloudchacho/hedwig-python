from typing import Any

from hedwig.models import Message


class HedwigBaseValidator:
    def deserialize(self, message_payload: str, provider_metadata: Any) -> Message:
        """
        Deserialize a message from the on-the-wire format
        :param message_payload: Raw message payload as received from the backend
        :param provider_metadata: Provider specific metadata
        :returns: Message object if valid
        :raise: :class:`hedwig.ValidationError` if validation fails.
        """
        raise NotImplementedError

    def serialize(self, message: Message) -> str:
        """
        Serialize a message for appropriate on-the-wire format
        :return: Message payload
        """
        raise NotImplementedError
