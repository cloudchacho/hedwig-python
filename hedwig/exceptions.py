import typing


class RetryException(Exception):
    """
    Special exception that does not log an exception when it is received.
    This is a retryable error.
    """

    def __init__(self, *args, **kwargs) -> None:
        pass


class LoggingException(Exception):
    """
    An exception that allows passing additional logging info. `extra` must be a dict that will be passed to
    `logging.exception` and can be used by a logging adaptor etc.
    """

    def __init__(self, message, extra: typing.Optional[typing.Dict] = None) -> None:
        super().__init__(message)
        self.extra = extra


class IgnoreException(Exception):
    """
    Indicates that this task should be ignored.
    """

    pass


class ValidationError(Exception):
    """
    Message failed JSON schema validation
    """

    pass


class ConfigurationError(Exception):
    """
    There was some problem with settings
    """

    pass


class CallbackNotFound(Exception):
    """
    No callback found that can handle the given message. Check your `CALLBACKS` settings.
    """

    pass
