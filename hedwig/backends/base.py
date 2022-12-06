import abc
import logging
import threading
import uuid
from concurrent.futures import Future
from contextlib import contextmanager
from typing import Optional, Union, Generator, List, Any, Dict, Tuple, Iterator

from hedwig.conf import settings
from hedwig.exceptions import ValidationError, IgnoreException, LoggingException, RetryException
from hedwig.models import Message
from hedwig.utils import log


class HedwigPublisherBaseBackend:
    @classmethod
    def topic(cls, message: Message) -> Union[str, Tuple[str, str]]:
        """
        The topic name for routing the message. When publishing cross-project topics, returned value may be a tuple of
        topic name and project id for Google or account id for AWS.
        """
        version_pattern = f'{message.major_version}.*'
        return settings.HEDWIG_MESSAGE_ROUTING[(message.type, version_pattern)]

    def _dispatch_sync(self, message: Message) -> None:
        from hedwig.backends.utils import get_consumer_backend

        consumer_backend = get_consumer_backend()
        queue_message = self._mock_queue_message(message)
        settings.HEDWIG_PRE_PROCESS_HOOK(**consumer_backend.pre_process_hook_kwargs(queue_message))
        consumer_backend.process_message(queue_message)
        settings.HEDWIG_POST_PROCESS_HOOK(**consumer_backend.post_process_hook_kwargs(queue_message))

    @abc.abstractmethod
    def _mock_queue_message(self, message: Message):
        """
        Generate a mock queue message in proper format as expected by the transport backend. This is primarily used for
        testing.
        """

    @abc.abstractmethod
    def _publish(self, message: Message, payload: Union[str, bytes], attributes: Dict[str, str]) -> Union[str, Future]:
        """
        Actually publish a message with the given payload and attributes. Some transport mechanisms restrict payload
        to string formats, and others may require bytes. It's up to the implementing class to encode the payload
        properly. The implementing class is responsible for decoding the payload back to the same format (bytes or
        string) as serialized by the validator.
        """

    @contextmanager
    def _maybe_instrument(self, message: Message, instrumentation_headers: Dict) -> Iterator:
        try:
            import hedwig.instrumentation

            with hedwig.instrumentation.on_publish(message, instrumentation_headers) as span:
                yield span
        except ImportError:
            yield None

    def publish(self, message: Message) -> Union[str, Future]:
        """
        Publish a message
        :return: Either a future if publisher is async, message id otherwise. If a future is returned, it'll result in
        message id once completed
        """
        if settings.HEDWIG_SYNC:
            self._dispatch_sync(message)
            return str(uuid.uuid4())

        default_headers = settings.HEDWIG_DEFAULT_HEADERS(message=message)
        if default_headers:
            new_headers = {**default_headers, **message.headers}
            message = message.with_headers(new_headers)

        instrumentation_headers: Dict[str, str] = {}
        with self._maybe_instrument(message, instrumentation_headers):
            new_headers = {**message.headers, **instrumentation_headers}
            message = message.with_headers(new_headers)

            payload, attributes = message.serialize()

            result = self._publish(message, payload, attributes)

            log_published_message(message, result)

        return result


class HedwigConsumerBaseBackend:
    def __init__(self) -> None:
        self._error_count = 0

    @staticmethod
    def pre_process_hook_kwargs(queue_message) -> dict:
        return {}

    @staticmethod
    def post_process_hook_kwargs(queue_message) -> dict:
        return {}

    @contextmanager
    def _maybe_instrument(self, **kwargs) -> Iterator:
        try:
            import hedwig.instrumentation

            with hedwig.instrumentation.on_receive(**kwargs) as span:
                yield span
        except ImportError:
            yield None

    def _maybe_update_instrumentation(self, message: Message) -> None:
        try:
            import hedwig.instrumentation

            hedwig.instrumentation.on_message(message)
        except ImportError:
            pass

    def message_handler(self, message_payload: Union[str, bytes], attributes: dict, provider_metadata) -> None:
        message = self._build_message(message_payload, attributes, provider_metadata)
        _log_received_message(message)

        self._maybe_update_instrumentation(message)

        message.exec_callback()

    def fetch_and_process_messages(
        self,
        num_messages: int = 10,
        visibility_timeout: Optional[int] = None,
        shutdown_event: Optional[threading.Event] = None,
    ) -> None:
        if not shutdown_event:
            shutdown_event = threading.Event()  # pragma: no cover
        while not shutdown_event.is_set():
            queue_messages = self.pull_messages(
                num_messages=num_messages, visibility_timeout=visibility_timeout, shutdown_event=shutdown_event
            )
            for queue_message in queue_messages:
                with self._maybe_instrument(**self.pre_process_hook_kwargs(queue_message)):
                    try:
                        settings.HEDWIG_PRE_PROCESS_HOOK(**self.pre_process_hook_kwargs(queue_message))
                    except Exception:
                        log(
                            __name__,
                            logging.ERROR,
                            'Exception in pre process hook for message',
                            exc_info=True,
                            extra={'queue_message': queue_message},
                        )
                        self.nack_message(queue_message)
                        continue

                    try:
                        self.process_message(queue_message)
                        if self._error_count:  # type: ignore
                            self._error_count = 0
                    except IgnoreException:
                        log(__name__, logging.INFO, 'Ignoring task', extra={'queue_message': queue_message})
                    except LoggingException as e:
                        # log with message and extra
                        log(__name__, logging.ERROR, str(e), extra=e.extra, exc_info=True)
                        self.nack_message(queue_message)
                        continue
                    except RetryException:
                        # Retry without logging exception
                        log(__name__, logging.INFO, 'Retrying due to exception')
                        self.nack_message(queue_message)
                        continue
                    except Exception:
                        log(__name__, logging.ERROR, 'Exception while processing message', exc_info=True)
                        self.nack_message(queue_message)
                        self._error_count += 1
                        continue

                    try:
                        settings.HEDWIG_POST_PROCESS_HOOK(**self.post_process_hook_kwargs(queue_message))
                    except Exception:
                        log(
                            __name__,
                            logging.ERROR,
                            'Exception in post process hook for message',
                            extra={'queue_message': queue_message},
                            exc_info=True,
                        )
                        self.nack_message(queue_message)
                        continue

                    try:
                        self.ack_message(queue_message)
                    except Exception:
                        log(
                            __name__,
                            logging.ERROR,
                            'Exception while deleting message',
                            extra={'queue_message': queue_message},
                            exc_info=True,
                        )

    def extend_visibility_timeout(self, visibility_timeout_s: int, metadata) -> None:
        """
        Extends visibility timeout of a message on a given priority queue for long running tasks.
        """
        raise NotImplementedError

    def requeue_dead_letter(self, num_messages: int = 10, visibility_timeout: Optional[int] = None) -> None:
        """
        Re-queues everything in the Hedwig DLQ back into the Hedwig queue.

        :param num_messages: Maximum number of messages to fetch in one call. Defaults to 10.
        :param visibility_timeout: The number of seconds the message should remain invisible to other queue readers.
        Defaults to None, which is queue default
        """
        raise NotImplementedError

    def pull_messages(
        self,
        num_messages: int = 10,
        visibility_timeout: Optional[int] = None,
        shutdown_event: Optional[threading.Event] = None,
    ) -> Union[Generator, List]:
        """
        Pulls messages from the cloud for this app.
        :param shutdown_event:
        :param num_messages:
        :param visibility_timeout:
        :return: a tuple of list of messages and the queue they were pulled from
        """
        raise NotImplementedError

    def process_message(self, queue_message) -> None:
        raise NotImplementedError

    def process_messages(self, lambda_event) -> None:
        # for lambda backend
        raise NotImplementedError

    def ack_message(self, queue_message) -> None:
        raise NotImplementedError

    def nack_message(self, queue_message) -> None:
        raise NotImplementedError

    @staticmethod
    def _build_message(message_payload: Union[str, bytes], attributes: dict, provider_metadata: Any) -> Message:
        try:
            message = Message.deserialize(message_payload, attributes, provider_metadata)
            # side-effect: validates the callback
            _ = message.callback
            return message
        except ValidationError:
            _log_invalid_message(message_payload)
            raise

    @property
    def error_count(self) -> int:
        """
        Returns the number of consecutive errors occurred when trying to process messages from the queue.

        Resets to 0 when a message is successfully processed.

        :return: Number of consecutive errors
        """
        return self._error_count


def log_published_message(message: Message, result: Union[str, Future]) -> None:
    def _log(message_id: str):
        log(__name__, logging.DEBUG, 'Sent message', extra={'hedwig_message': message, 'message_id': message_id})

    if isinstance(result, Future):
        result.add_done_callback(lambda f: _log(f.result()))
    else:
        _log(result)


def _log_received_message(message: Message) -> None:
    log(__name__, logging.DEBUG, 'Received message', extra={'hedwig_message': message})


def _log_invalid_message(message_payload: Union[str, bytes]) -> None:
    log(__name__, logging.ERROR, 'Received invalid message', extra={'message_payload': message_payload})
