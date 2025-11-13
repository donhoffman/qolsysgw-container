import asyncio
import unittest
from unittest import mock

import tests.unit.qolsysgw.mqtt.testenv  # noqa: F401

from apps.qolsysgw.mqtt.client import MqttClient

import logging
logging.basicConfig(level=logging.DEBUG)


class TestUnitMqttClient(unittest.TestCase):
    """Test MqttClient functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = MqttClient(
            host="test.mqtt.broker",
            port=1883,
            username="testuser",
            password="testpass",
            will_topic="test/will",
            will_payload="offline",
            birth_topic="test/birth",
            birth_payload="online",
            qos=1,
            retain=True,
        )

    def test_init(self):
        """Test client initialization."""
        self.assertEqual(self.client.host, "test.mqtt.broker")
        self.assertEqual(self.client.port, 1883)
        self.assertEqual(self.client.username, "testuser")
        self.assertEqual(self.client.password, "testpass")
        self.assertEqual(self.client.will_topic, "test/will")
        self.assertEqual(self.client.will_payload, "offline")
        self.assertEqual(self.client.birth_topic, "test/birth")
        self.assertEqual(self.client.birth_payload, "online")
        self.assertEqual(self.client.qos, 1)
        self.assertEqual(self.client.retain, True)
        self.assertFalse(self.client.connected)

    def test_topic_matches_exact(self):
        """Test exact topic matching."""
        self.assertTrue(
            MqttClient._topic_matches("home/living/temperature", "home/living/temperature")
        )
        self.assertFalse(
            MqttClient._topic_matches("home/living/temperature", "home/living/humidity")
        )

    def test_topic_matches_single_level_wildcard(self):
        """Test single level wildcard (+) matching."""
        self.assertTrue(
            MqttClient._topic_matches("home/living/temperature", "home/+/temperature")
        )
        self.assertTrue(
            MqttClient._topic_matches("home/bedroom/temperature", "home/+/temperature")
        )
        self.assertFalse(
            MqttClient._topic_matches("home/living/room/temperature", "home/+/temperature")
        )

    def test_topic_matches_multi_level_wildcard(self):
        """Test multi level wildcard (#) matching."""
        self.assertTrue(
            MqttClient._topic_matches("home/living/temperature", "home/#")
        )
        self.assertTrue(
            MqttClient._topic_matches("home/living/room/temperature", "home/#")
        )
        self.assertTrue(
            MqttClient._topic_matches("home/bedroom", "home/#")
        )
        self.assertFalse(
            MqttClient._topic_matches("office/living/temperature", "home/#")
        )

    @mock.patch('apps.qolsysgw.mqtt.client.Client')
    async def test_connect(self, mock_client_class):
        """Test MQTT connection."""
        mock_client_instance = mock.AsyncMock()
        mock_client_class.return_value = mock_client_instance

        await self.client.connect()

        # Verify Client was instantiated with correct parameters
        mock_client_class.assert_called_once()
        call_kwargs = mock_client_class.call_args[1]
        self.assertEqual(call_kwargs['hostname'], "test.mqtt.broker")
        self.assertEqual(call_kwargs['port'], 1883)
        self.assertEqual(call_kwargs['username'], "testuser")
        self.assertEqual(call_kwargs['password'], "testpass")
        self.assertIsNotNone(call_kwargs['will'])

        # Verify connection was established
        mock_client_instance.__aenter__.assert_called_once()
        self.assertTrue(self.client.connected)

        # Verify birth message was published
        mock_client_instance.publish.assert_called_once_with(
            "test/birth",
            payload="online",
            qos=1,
            retain=True,
        )

    @mock.patch('apps.qolsysgw.mqtt.client.Client')
    async def test_connect_without_will(self, mock_client_class):
        """Test MQTT connection without LWT."""
        client = MqttClient(
            host="test.mqtt.broker",
            port=1883,
            will_topic=None,
            birth_topic=None,
        )

        mock_client_instance = mock.AsyncMock()
        mock_client_class.return_value = mock_client_instance

        await client.connect()

        # Verify Client was instantiated without will
        call_kwargs = mock_client_class.call_args[1]
        self.assertIsNone(call_kwargs['will'])

        # Verify no birth message was published
        mock_client_instance.publish.assert_not_called()

    @mock.patch('apps.qolsysgw.mqtt.client.Client')
    async def test_disconnect(self, mock_client_class):
        """Test MQTT disconnection."""
        mock_client_instance = mock.AsyncMock()
        mock_client_class.return_value = mock_client_instance

        await self.client.connect()
        await self.client.disconnect()

        # Verify disconnection
        mock_client_instance.__aexit__.assert_called_once_with(None, None, None)
        self.assertFalse(self.client.connected)
        self.assertIsNone(self.client._client)

    @mock.patch('apps.qolsysgw.mqtt.client.Client')
    async def test_publish(self, mock_client_class):
        """Test publishing messages."""
        mock_client_instance = mock.AsyncMock()
        mock_client_class.return_value = mock_client_instance

        await self.client.connect()

        # Clear birth message publish call
        mock_client_instance.publish.reset_mock()

        # Test publish with default qos and retain
        await self.client.publish("test/topic", "test payload")

        mock_client_instance.publish.assert_called_once_with(
            "test/topic",
            payload="test payload",
            qos=1,
            retain=True,
        )

    @mock.patch('apps.qolsysgw.mqtt.client.Client')
    async def test_publish_custom_qos_retain(self, mock_client_class):
        """Test publishing with custom qos and retain."""
        mock_client_instance = mock.AsyncMock()
        mock_client_class.return_value = mock_client_instance

        await self.client.connect()
        mock_client_instance.publish.reset_mock()

        # Test publish with custom qos and retain
        await self.client.publish("test/topic", "test payload", qos=2, retain=False)

        mock_client_instance.publish.assert_called_once_with(
            "test/topic",
            payload="test payload",
            qos=2,
            retain=False,
        )

    @mock.patch('apps.qolsysgw.mqtt.client.Client')
    async def test_publish_not_connected(self, mock_client_class):
        """Test publishing when not connected (should log warning and return)."""
        # Don't connect
        await self.client.publish("test/topic", "test payload")

        # Should not raise, just log warning
        # Since we're not connected, _client is None and publish should return early

    @mock.patch('apps.qolsysgw.mqtt.client.Client')
    async def test_subscribe(self, mock_client_class):
        """Test subscribing to topics."""
        mock_client_instance = mock.AsyncMock()
        mock_client_class.return_value = mock_client_instance

        callback = mock.AsyncMock()

        await self.client.connect()

        # Subscribe to topic
        await self.client.subscribe("test/topic", callback)

        # Verify subscription
        self.assertIn("test/topic", self.client._subscriptions)
        self.assertEqual(self.client._subscriptions["test/topic"], callback)
        mock_client_instance.subscribe.assert_called_once_with("test/topic", qos=1)

    @mock.patch('apps.qolsysgw.mqtt.client.Client')
    async def test_subscribe_before_connect(self, mock_client_class):
        """Test subscribing before connection (should store but not subscribe yet)."""
        callback = mock.AsyncMock()

        # Subscribe before connecting
        await self.client.subscribe("test/topic", callback)

        # Should store subscription but not call client.subscribe
        self.assertIn("test/topic", self.client._subscriptions)

    @mock.patch('apps.qolsysgw.mqtt.client.Client')
    async def test_resubscribe_on_connect(self, mock_client_class):
        """Test that subscriptions are restored on reconnect."""
        mock_client_instance = mock.AsyncMock()
        mock_client_class.return_value = mock_client_instance

        callback1 = mock.AsyncMock()
        callback2 = mock.AsyncMock()

        # Subscribe before connecting
        await self.client.subscribe("test/topic1", callback1)
        await self.client.subscribe("test/topic2", callback2)

        # Connect
        await self.client.connect()

        # Verify both subscriptions were made
        self.assertEqual(mock_client_instance.subscribe.call_count, 2)
        mock_client_instance.subscribe.assert_any_call("test/topic1", qos=1)
        mock_client_instance.subscribe.assert_any_call("test/topic2", qos=1)

    @mock.patch('apps.qolsysgw.mqtt.client.Client')
    async def test_unsubscribe(self, mock_client_class):
        """Test unsubscribing from topics."""
        mock_client_instance = mock.AsyncMock()
        mock_client_class.return_value = mock_client_instance

        callback = mock.AsyncMock()

        await self.client.connect()
        await self.client.subscribe("test/topic", callback)

        # Unsubscribe
        await self.client.unsubscribe("test/topic")

        # Verify unsubscription
        self.assertNotIn("test/topic", self.client._subscriptions)
        mock_client_instance.unsubscribe.assert_called_once_with("test/topic")

    @mock.patch('apps.qolsysgw.mqtt.client.Client')
    async def test_message_listener_dispatches_to_callback(self, mock_client_class):
        """Test that message listener dispatches messages to callbacks."""
        mock_client_instance = mock.AsyncMock()
        mock_client_class.return_value = mock_client_instance

        # Mock message
        mock_message = mock.Mock()
        mock_message.topic = "test/topic"
        mock_message.payload = b"test payload"

        # Make messages async iterable
        async def mock_messages():
            yield mock_message

        mock_client_instance.messages = mock_messages()

        callback = mock.AsyncMock()

        await self.client.connect()
        await self.client.subscribe("test/topic", callback)

        # Start listener task
        listener_task = asyncio.create_task(self.client._message_listener())

        # Give it time to process the message
        await asyncio.sleep(0.1)

        # Cancel the task
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass

        # Verify callback was called
        callback.assert_called_once_with("test/topic", "test payload")

    @mock.patch('apps.qolsysgw.mqtt.client.Client')
    async def test_message_listener_handles_callback_exception(self, mock_client_class):
        """Test that message listener continues after callback exception."""
        mock_client_instance = mock.AsyncMock()
        mock_client_class.return_value = mock_client_instance

        # Mock messages
        mock_message1 = mock.Mock()
        mock_message1.topic = "test/topic"
        mock_message1.payload = b"message1"

        mock_message2 = mock.Mock()
        mock_message2.topic = "test/topic"
        mock_message2.payload = b"message2"

        # Make messages async iterable
        async def mock_messages():
            yield mock_message1
            yield mock_message2

        mock_client_instance.messages = mock_messages()

        # Callback that raises exception on first call
        callback = mock.AsyncMock()
        callback.side_effect = [Exception("Test error"), None]

        await self.client.connect()
        await self.client.subscribe("test/topic", callback)

        # Start listener task
        listener_task = asyncio.create_task(self.client._message_listener())

        # Give it time to process messages
        await asyncio.sleep(0.1)

        # Cancel the task
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass

        # Verify both callbacks were attempted
        self.assertEqual(callback.call_count, 2)


def async_test(coro):
    """Decorator to run async tests."""
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro(*args, **kwargs))
        finally:
            loop.close()
    return wrapper


# Apply async_test decorator to all async test methods
for name in dir(TestUnitMqttClient):
    if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(TestUnitMqttClient, name)):
        setattr(
            TestUnitMqttClient,
            name,
            async_test(getattr(TestUnitMqttClient, name))
        )


if __name__ == '__main__':
    unittest.main()
