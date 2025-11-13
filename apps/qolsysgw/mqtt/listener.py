"""MQTT listeners for Qolsys events and control messages."""

import json
import logging
from typing import Callable, Optional

from apps.qolsysgw.mqtt.client import MqttClient
from apps.qolsysgw.qolsys.control import QolsysControl
from apps.qolsysgw.qolsys.events import QolsysEvent
from apps.qolsysgw.qolsys.exceptions import UnknownQolsysControlException
from apps.qolsysgw.qolsys.exceptions import UnknownQolsysEventException


LOGGER = logging.getLogger(__name__)


class MqttListener:
    """Base MQTT listener class."""

    def __init__(
        self,
        mqtt_client: MqttClient,
        topic: str,
        callback: Optional[Callable] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize MQTT listener.

        Args:
            mqtt_client: MQTT client instance
            topic: MQTT topic to subscribe to
            callback: Callback function for parsed messages
            logger: Logger instance (optional)
        """
        self._mqtt_client = mqtt_client
        self._topic = topic
        self._callback = callback
        self._logger = logger or LOGGER

    async def start(self) -> None:
        """Start listening to MQTT topic."""
        await self._mqtt_client.subscribe(self._topic, self._message_callback)
        self._logger.info(f"Started listening to {self._topic}")

    async def _message_callback(self, topic: str, payload: str) -> None:
        """Internal callback that receives raw MQTT messages.

        Subclasses should override event_callback() instead.

        Args:
            topic: MQTT topic
            payload: Message payload
        """
        await self.event_callback(topic, payload)

    async def event_callback(self, topic: str, payload: str) -> None:
        """Process MQTT message. Override in subclasses.

        Args:
            topic: MQTT topic
            payload: Message payload
        """
        raise NotImplementedError("Subclasses must implement event_callback()")


class MqttQolsysEventListener(MqttListener):
    """Listener for Qolsys panel events published to MQTT."""

    async def event_callback(self, topic: str, payload: str) -> None:
        """Parse and process Qolsys event from MQTT.

        Args:
            topic: MQTT topic
            payload: JSON event payload
        """
        self._logger.debug(f'Received event on {topic}: {payload}')

        if not payload:
            self._logger.warning(f'Received empty event on {topic}')
            return

        try:
            # Parse the event to one of our event classes
            event = QolsysEvent.from_json(payload)
        except json.decoder.JSONDecodeError:
            self._logger.debug(f'Payload is not JSON: {payload}')
            return
        except UnknownQolsysEventException:
            self._logger.debug(f'Unknown Qolsys event: {payload}')
            return

        # Call the user callback if provided
        if self._callback:
            # noinspection PyBroadException
            try:
                await self._callback(event)
            except Exception:
                self._logger.exception(f'Error calling callback for event: {event}')


class MqttQolsysControlListener(MqttListener):
    """Listener for control commands from Home Assistant via MQTT."""

    async def event_callback(self, topic: str, payload: str) -> None:
        """Parse and process control command from MQTT.

        Args:
            topic: MQTT topic
            payload: JSON control payload
        """
        self._logger.debug(f'Received control on {topic}: {payload}')

        if not payload:
            self._logger.warning(f'Received empty control on {topic}')
            return

        try:
            # Parse the control command
            control = QolsysControl.from_json(payload)
        except json.decoder.JSONDecodeError:
            self._logger.debug(f'Payload is not JSON: {payload}')
            return
        except UnknownQolsysControlException:
            self._logger.debug(f'Unknown Qolsys control: {payload}')
            return

        # Call the user callback if provided
        if self._callback:
            # noinspection PyBroadException
            try:
                await self._callback(control)
            except Exception:
                self._logger.exception(f'Error calling callback for control: {control}')
