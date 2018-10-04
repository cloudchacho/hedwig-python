import inspect
import typing

from hedwig.exceptions import ConfigurationError, CallbackNotFound
from hedwig.models import Message, MessageType
from hedwig.conf import settings


class Callback:
    def __init__(self, fn: typing.Callable) -> None:
        self._fn = fn
        signature = inspect.signature(fn)
        message_found = False
        for p in signature.parameters.values():
            # if **kwargs is specified, just pass all things by default since function can always inspect arg names
            if p.kind == inspect.Parameter.VAR_KEYWORD:
                # disallow use of *kwargs
                raise ConfigurationError("Use of **kwargs is not allowed")
            elif p.kind == inspect.Parameter.VAR_POSITIONAL:
                # disallow use of *args
                raise ConfigurationError("Use of *args is not allowed")
            elif p.name == 'message':
                if p.annotation is not inspect.Signature.empty and p.annotation is not Message:
                    raise ConfigurationError("Signature for 'message' param must be `hedwig.Message`")
                message_found = True
            else:
                raise ConfigurationError(f"Unknown param '{p.name}' not allowed")

        if not message_found:
            raise ConfigurationError("Callback must accept a parameter called 'message'")

    @property
    def fn(self) -> typing.Callable:
        """"
        return: Task function
        """
        return self._fn

    def call(self, message: Message) -> None:
        """
        Calls the task with this message

        :param message: The message
        """
        self.fn(message)

    def __str__(self) -> str:
        return f'Hedwig task: {self.fn.__name__}'

    @classmethod
    def find_by_message(cls, msg_type: MessageType, major_version: int) -> 'Callback':
        """
        Finds a callback by message type
        :return: Callback
        :raises CallbackNotFound: if task isn't registered
        """
        version_pattern = f'{major_version}.*'
        if (msg_type, version_pattern) in _ALL_CALLBACKS:
            return _ALL_CALLBACKS[(msg_type, version_pattern)]

        raise CallbackNotFound(msg_type, major_version)


_ALL_CALLBACKS = {(MessageType(k[0]), k[1]): Callback(v) for k, v in settings.HEDWIG_CALLBACKS.items()}
