pytest_plugins = ["pytester"]


def test_plugin(testdir):
    testdir.makeconftest(
        """
        import pytest

        from hedwig.models import Message, MessageType
        from hedwig.testing.factories import MessageFactory


        @pytest.fixture(name='message_data')
        def _message_data():
            return MessageFactory.build(msg_type=MessageType.trip_created)


        @pytest.fixture()
        def message(message_data):
            return Message(message_data)
    """
    )

    # create a temporary pytest test file
    testdir.makepyfile(
        """
        from hedwig.models import MessageType


        def test_mock_hedwig_publish_no_publish(mock_hedwig_publish):
            mock_hedwig_publish.assert_message_not_published(MessageType.trip_created)


        def test_mock_hedwig_publish_publish_check(mock_hedwig_publish, message):
            message.publish()
            mock_hedwig_publish.assert_message_not_published(MessageType.device_created)


        def test_mock_hedwig_publish_published(mock_hedwig_publish, message):
            message.publish()
            mock_hedwig_publish.assert_message_published(message.type, data=message.data, version=message.data_schema_version)
    """
    )

    # run all tests with pytest
    result = testdir.runpytest()

    # check that all 3 tests passed
    result.assert_outcomes(passed=3)
