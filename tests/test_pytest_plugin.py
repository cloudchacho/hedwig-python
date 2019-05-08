pytest_plugins = ["pytester"]


def test_plugin(testdir):
    testdir.makeconftest(
        """
        import pytest

        import hedwig.conf
        from hedwig import models
        from hedwig.models import Message, MessageType
        from hedwig.testing.factories import MessageFactory


        @pytest.fixture(autouse=True, params=['aws', 'google'])
        def providers(request, settings):
            if request.param == 'aws':
                settings.HEDWIG_PUBLISHER_BACKEND = 'hedwig.backends.aws.AWSSNSPublisherBackend'
                settings.HEDWIG_CONSUMER_BACKEND = 'hedwig.backends.aws.AWSSQSConsumerBackend'
            elif request.param == 'google':
                settings.GOOGLE_APPLICATION_CREDENTIALS = "DUMMY_GOOGLE_APPLICATION_CREDENTIALS"
                settings.HEDWIG_PUBLISHER_BACKEND = "hedwig.backends.gcp.GooglePubSubPublisherBackend"
                settings.HEDWIG_CONSUMER_BACKEND = "hedwig.backends.gcp.GooglePubSubConsumerBackend"
                settings.GOOGLE_PUBSUB_PROJECT_ID = "DUMMY_PROJECT_ID"
                settings.GOOGLE_PUBSUB_READ_TIMEOUT_S = 5
                settings.HEDWIG_GOOGLE_MESSAGE_RETRY_STATE_BACKEND = 'hedwig.backends.gcp.MessageRetryStateLocMem'
                settings.HEDWIG_GOOGLE_MESSAGE_MAX_RETRIES = 5

        @pytest.fixture(name='message_data')
        def _message_data():
            return MessageFactory.build(msg_type=MessageType.trip_created)

        @pytest.fixture
        def message(message_data):
            return Message(message_data)

        @pytest.fixture(name='other_message_data')
        def _other_message_data():
            return MessageFactory.build(msg_type=MessageType.trip_created)

        @pytest.fixture
        def settings():
            overrides = {}
            original_module = hedwig.conf.settings._user_settings

            class Wrapped:
                def __getattr__(self, name):
                    return overrides.get(name, getattr(original_module, name))

            hedwig.conf.settings._user_settings = Wrapped()
            hedwig.conf.settings.clear_cache()
            # in case a test overrides HEDWIG_DATA_VALIDATOR_CLASS
            models._validator = None

            try:
                yield hedwig.conf.settings._user_settings
            finally:
                hedwig.conf.settings._user_settings = original_module
                hedwig.conf.settings.clear_cache()
                # in case a test overrides HEDWIG_DATA_VALIDATOR_CLASS
                models._validator = None
    """
    )

    # create a temporary pytest test file
    testdir.makepyfile(
        """
        from hedwig.models import MessageType


        def test_mock_hedwig_publish_no_publish(settings, mock_hedwig_publish):
            mock_hedwig_publish.assert_message_not_published(MessageType.trip_created)


        def test_mock_hedwig_publish_publish_check(mock_hedwig_publish, message):
            message.publish()
            mock_hedwig_publish.assert_message_not_published(MessageType.device_created)


        def test_mock_hedwig_publish_publish_check_same_type(mock_hedwig_publish, message, other_message_data):
            message.publish()
            mock_hedwig_publish.assert_message_not_published(message.type, data=other_message_data)
            mock_hedwig_publish.assert_message_published(
                message.type, data=message.data, version=message.data_schema_version)


        def test_mock_hedwig_publish_published(mock_hedwig_publish, message):
            message.publish()
            mock_hedwig_publish.assert_message_published(
                message.type, data=message.data, version=message.data_schema_version)


        def test_mock_hedwig_publish_published_without_checking_data(mock_hedwig_publish, message):
            message.publish()
            mock_hedwig_publish.assert_message_published(message.type, version=message.data_schema_version)
    """
    )

    # run all tests with pytest
    result = testdir.runpytest()

    # check that all tests passed
    result.assert_outcomes(passed=10)
