"""MQTT client wrapper using aiomqtt."""

import asyncio
import logging
from typing import Callable, Optional

from aiomqtt import Client, MqttError, Will

LOGGER = logging.getLogger(__name__)


class MqttClient:
    """Async MQTT client wrapper with auto-reconnect support."""

    def __init__(
        self,
        host: str,
        port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        will_topic: Optional[str] = None,
        will_payload: str = "offline",
        birth_topic: Optional[str] = None,
        birth_payload: str = "online",
        qos: int = 1,
        retain: bool = True,
    ):
        """Initialize MQTT client.

        Args:
            host: MQTT broker hostname
            port: MQTT broker port
            username: MQTT username (optional)
            password: MQTT password (optional)
            will_topic: Last will topic (optional)
            will_payload: Last will payload
            birth_topic: Birth message topic (optional)
            birth_payload: Birth message payload
            qos: Default QoS level (0-2)
            retain: Retain messages by default
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.will_topic = will_topic
        self.will_payload = will_payload
        self.birth_topic = birth_topic
        self.birth_payload = birth_payload
        self.qos = qos
        self.retain = retain

        self._client: Optional[Client] = None
        self._subscriptions: dict[str, Callable] = {}
        self._connected = False
        self._reconnect_interval = 5  # seconds
        self._message_task: Optional[asyncio.Task] = None

    @property
    def connected(self) -> bool:
        """Return connection status."""
        return self._connected

    async def connect(self) -> None:
        """Connect to MQTT broker with LWT support."""
        will = None
        if self.will_topic:
            will = Will(
                topic=self.will_topic,
                payload=self.will_payload,
                qos=self.qos,
                retain=self.retain,
            )

        LOGGER.info(f"Connecting to MQTT broker at {self.host}:{self.port}")

        self._client = Client(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            will=will,
        )

        await self._client.__aenter__()
        self._connected = True

        LOGGER.info("Connected to MQTT broker")

        # Publish birth message
        if self.birth_topic:
            await self.publish(
                self.birth_topic,
                self.birth_payload,
                retain=self.retain,
            )
            LOGGER.info(f"Published birth message to {self.birth_topic}")

        # Resubscribe to all topics
        if self._subscriptions:
            LOGGER.info(f"Resubscribing to {len(self._subscriptions)} topics")
            for topic in self._subscriptions.keys():
                await self._client.subscribe(topic, qos=self.qos)
                LOGGER.debug(f"Subscribed to {topic}")

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        if self._message_task:
            self._message_task.cancel()
            try:
                await self._message_task
            except asyncio.CancelledError:
                pass
            self._message_task = None

        if self._client:
            LOGGER.info("Disconnecting from MQTT broker")
            self._connected = False
            await self._client.__aexit__(None, None, None)
            self._client = None
            LOGGER.info("Disconnected from MQTT broker")

    async def publish(
        self,
        topic: str,
        payload: str,
        qos: Optional[int] = None,
        retain: Optional[bool] = None,
    ) -> None:
        """Publish message to MQTT topic.

        Args:
            topic: MQTT topic
            payload: Message payload
            qos: QoS level (uses default if not specified)
            retain: Retain flag (uses default if not specified)
        """
        if not self._client or not self._connected:
            LOGGER.warning(f"Cannot publish to {topic}: not connected")
            return

        qos = qos if qos is not None else self.qos
        retain = retain if retain is not None else self.retain

        try:
            await self._client.publish(
                topic,
                payload=payload,
                qos=qos,
                retain=retain,
            )
            LOGGER.debug(f"Published to {topic}: {payload}")
        except MqttError as e:
            LOGGER.error(f"Failed to publish to {topic}: {e}")
            raise

    async def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to MQTT topic with callback.

        Args:
            topic: MQTT topic pattern
            callback: Async callback function(topic, payload)
        """
        self._subscriptions[topic] = callback

        if self._client and self._connected:
            await self._client.subscribe(topic, qos=self.qos)
            LOGGER.info(f"Subscribed to {topic}")

    async def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from MQTT topic.

        Args:
            topic: MQTT topic pattern
        """
        if topic in self._subscriptions:
            del self._subscriptions[topic]

        if self._client and self._connected:
            await self._client.unsubscribe(topic)
            LOGGER.info(f"Unsubscribed from {topic}")

    async def _message_listener(self) -> None:
        """Listen for incoming MQTT messages and dispatch to callbacks."""
        if not self._client:
            return

        LOGGER.info("Starting MQTT message listener")

        try:
            async for message in self._client.messages:
                topic = str(message.topic)
                payload = message.payload.decode()

                LOGGER.debug(f"Received message on {topic}: {payload}")

                # Find matching subscription and call callback
                for sub_topic, callback in self._subscriptions.items():
                    if self._topic_matches(topic, sub_topic):
                        # noinspection PyBroadException
                        try:
                            await callback(topic, payload)
                        except Exception:  # noinspection PyBroadException - user callback can raise anything
                            LOGGER.error(
                                f"Error in callback for {topic}: {payload}",
                                exc_info=True,
                            )
        except asyncio.CancelledError:
            LOGGER.info("MQTT message listener cancelled")
            raise
        except Exception as e:
            LOGGER.error(f"Error in message listener: {e}", exc_info=True)
            raise

    @staticmethod
    def _topic_matches(topic: str, pattern: str) -> bool:
        """Check if topic matches subscription pattern.

        Args:
            topic: Actual topic
            pattern: Subscription pattern (may contain wildcards)

        Returns:
            True if topic matches pattern
        """
        # Simple wildcard matching for MQTT topics
        # + matches single level, # matches multiple levels

        topic_parts = topic.split("/")
        pattern_parts = pattern.split("/")

        # # must be last and matches everything
        if pattern_parts[-1] == "#":
            return topic_parts[: len(pattern_parts) - 1] == pattern_parts[:-1]

        if len(topic_parts) != len(pattern_parts):
            return False

        for topic_part, pattern_part in zip(topic_parts, pattern_parts):
            if pattern_part == "+":
                continue
            if pattern_part != topic_part:
                return False

        return True

    async def run_with_reconnect(self) -> None:
        """Run MQTT client with automatic reconnection.

        This method handles connection and automatic reconnection on failure.
        It should be run as a long-lived task.
        """
        while True:
            # noinspection PyBroadException
            try:
                if not self._connected:
                    await self.connect()

                # Start message listener
                if not self._message_task or self._message_task.done():
                    self._message_task = asyncio.create_task(self._message_listener())

                # Wait for message task to complete (it shouldn't unless there's an error)
                await self._message_task

            except asyncio.CancelledError:
                LOGGER.info("MQTT client task cancelled")
                await self.disconnect()
                raise

            except MqttError as e:
                LOGGER.error(f"MQTT error: {e}")
                self._connected = False

                if self._client:
                    # noinspection PyBroadException
                    try:
                        await self._client.__aexit__(None, None, None)
                    except Exception:
                        pass
                    self._client = None

                LOGGER.info(f"Reconnecting in {self._reconnect_interval} seconds...")
                await asyncio.sleep(self._reconnect_interval)

            except Exception:
                LOGGER.error("Unexpected error in MQTT client", exc_info=True)
                self._connected = False

                if self._client:
                    # noinspection PyBroadException
                    try:
                        await self._client.__aexit__(None, None, None)
                    except Exception:
                        pass
                    self._client = None

                LOGGER.info(f"Reconnecting in {self._reconnect_interval} seconds...")
                await asyncio.sleep(self._reconnect_interval)