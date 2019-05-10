import copy
import json
import logging
import typing
import uuid
from decimal import Decimal
from unittest import mock

from hedwig.backends.import_utils import import_class
from hedwig.conf import settings
from hedwig.exceptions import ValidationError, IgnoreException, LoggingException, RetryException
from hedwig.models import Message


logger = logging.getLogger(__name__)


class HedwigBaseBackend:
    @classmethod
    def build(cls, dotted_path: str, *args, **kwargs):
        """
        Import a dotted module path and return the backend class instance.
        Raise ImportError if the import failed.
        """
        backend_cls = import_class(dotted_path)
        return backend_cls(*args, **kwargs)

    @staticmethod
    def message_payload(data: dict) -> str:
        return json.dumps(data, default=_decimal_json_default)


class HedwigPublisherBaseBackend(HedwigBaseBackend):
    def _dispatch_sync(self, message: Message) -> None:
        from hedwig.backends.utils import get_consumer_backend

        consumer_backend = get_consumer_backend()
        queue_message = self._mock_queue_message(message)
        settings.HEDWIG_PRE_PROCESS_HOOK(**consumer_backend.pre_process_hook_kwargs(queue_message))
        consumer_backend.process_message(queue_message)
        settings.HEDWIG_POST_PROCESS_HOOK(**consumer_backend.post_process_hook_kwargs(queue_message))

    def _mock_queue_message(self, message: Message) -> mock.Mock:
        return NotImplementedError

    def _publish(self, message: Message, payload: str, headers: typing.Optional[typing.Mapping] = None) -> str:
        raise NotImplementedError

    def publish(self, message: Message) -> str:
        if settings.HEDWIG_SYNC:
            self._dispatch_sync(message)
            return str(uuid.uuid4())

        message_body = message.as_dict()
        headers = {**settings.HEDWIG_DEFAULT_HEADERS(message=message), **message_body['metadata']['headers']}
        # make a copy to prevent changing "headers" variable contents in
        # pre serialize hook
        message_body['metadata']['headers'] = copy.deepcopy(headers)
        settings.HEDWIG_PRE_SERIALIZE_HOOK(message_data=message_body)
        payload = self.message_payload(message_body)

        message_id = self._publish(message, payload, headers)

        log_published_message(message_body, message_id)

        return message_id


class HedwigConsumerBaseBackend(HedwigBaseBackend):
    @staticmethod
    def pre_process_hook_kwargs(queue_message) -> dict:
        return {}

    @staticmethod
    def post_process_hook_kwargs(queue_message) -> dict:
        return {}

    def message_handler(self, message_json: str, provider_metadata) -> None:
        message = self._build_message(message_json, provider_metadata)
        _log_received_message(message.as_dict())

        try:
            message.exec_callback()
        except IgnoreException:
            logger.info(f'Ignoring task {message.id}')
            return
        except LoggingException as e:
            # log with message and extra
            logger.exception(str(e), extra=e.extra)
            # let it bubble up so message ends up in DLQ
            raise
        except RetryException:
            # Retry without logging exception
            logger.info('Retrying due to exception')
            # let it bubble up so message ends up in DLQ
            raise
        except Exception:
            logger.exception(f'Exception while processing message')
            # let it bubble up so message ends up in DLQ
            raise

    def fetch_and_process_messages(self, num_messages: int = 1, visibility_timeout: int = None) -> None:
        queue_messages = self.pull_messages(num_messages, visibility_timeout)
        for queue_message in queue_messages:
            settings.HEDWIG_PRE_PROCESS_HOOK(**self.pre_process_hook_kwargs(queue_message))
            try:
                self.process_message(queue_message)
                try:
                    settings.HEDWIG_POST_PROCESS_HOOK(**self.post_process_hook_kwargs(queue_message))
                except Exception:
                    logger.exception(f'Exception in post process hook for message: {queue_message}')
                    raise
                try:
                    self.delete_message(queue_message)
                except Exception:
                    logger.exception(f'Exception while deleting message: {queue_message}')
            except Exception:
                # already logged in message_handler
                pass

    def extend_visibility_timeout(self, visibility_timeout_s: int, metadata) -> None:
        """
        Extends visibility timeout of a message on a given priority queue for long running tasks.
        """
        raise NotImplementedError

    def requeue_dead_letter(self, num_messages: int = 10, visibility_timeout: int = None) -> None:
        """
        Re-queues everything in the Hedwig DLQ back into the Hedwig queue.
        """
        raise NotImplementedError

    def pull_messages(self, num_messages: int = 1, visibility_timeout: int = None) -> typing.List:
        """
        Pulls messages from the cloud for this app.
        :param num_messages:
        :param visibility_timeout:
        :return: a tuple of list of messages and the queue they were pulled from
        """
        raise NotImplementedError

    def process_message(self, queue_message) -> None:
        raise NotImplementedError

    def delete_message(self, queue_message) -> None:
        raise NotImplementedError

    @staticmethod
    def _build_message(message_json: str, provider_metadata) -> Message:
        try:
            message_body = json.loads(message_json)
            settings.HEDWIG_POST_DESERIALIZE_HOOK(message_data=message_body)
            message = Message(json.loads(message_json))
            message.validate_callback()
            message.metadata.provider_metadata = provider_metadata
            return message
        except (ValidationError, ValueError):
            _log_invalid_message(message_json)
            raise


def _decimal_json_default(obj):
    if isinstance(obj, Decimal):
        int_val = int(obj)
        if int_val == obj:
            return int_val
        else:
            return float(obj)
    raise TypeError


def log_published_message(message_body: dict, message_id: str) -> None:
    logger.debug('Sent message', extra={'message_body': message_body, 'message_id': message_id})


def _log_received_message(message_body: dict) -> None:
    logger.debug('Received message', extra={'message_body': message_body})


def _log_invalid_message(message_json: str) -> None:
    logger.error('Received invalid message', extra={'message_json': message_json})
