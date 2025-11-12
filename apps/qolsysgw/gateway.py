"""Qolsys Gateway - Main gateway class for standalone operation."""

import asyncio
import logging
import uuid
from typing import Optional

from apps.qolsysgw.config import QolsysConfig
from apps.qolsysgw.mqtt.client import MqttClient
from apps.qolsysgw.mqtt.listener import MqttQolsysControlListener
from apps.qolsysgw.mqtt.listener import MqttQolsysEventListener
from apps.qolsysgw.mqtt.updater import MqttUpdater
from apps.qolsysgw.mqtt.updater import MqttWrapperFactory

from apps.qolsysgw.qolsys.control import QolsysControl
from apps.qolsysgw.qolsys.events import QolsysEvent
from apps.qolsysgw.qolsys.events import QolsysEventAlarm
from apps.qolsysgw.qolsys.events import QolsysEventArming
from apps.qolsysgw.qolsys.events import QolsysEventError
from apps.qolsysgw.qolsys.events import QolsysEventInfoSecureArm
from apps.qolsysgw.qolsys.events import QolsysEventInfoSummary
from apps.qolsysgw.qolsys.events import QolsysEventZoneEventActive
from apps.qolsysgw.qolsys.events import QolsysEventZoneEventAdd
from apps.qolsysgw.qolsys.events import QolsysEventZoneEventUpdate
from apps.qolsysgw.qolsys.exceptions import InvalidUserCodeException
from apps.qolsysgw.qolsys.exceptions import MissingUserCodeException
from apps.qolsysgw.qolsys.socket import QolsysSocket
from apps.qolsysgw.qolsys.state import QolsysState


LOGGER = logging.getLogger(__name__)


class QolsysGateway:
    """Standalone Qolsys Gateway without AppDaemon dependencies."""

    def __init__(self, config: QolsysConfig, mqtt_client: MqttClient):
        """Initialize the gateway.

        Args:
            config: Qolsys configuration
            mqtt_client: MQTT client instance
        """
        self._config = config
        self._mqtt_client = mqtt_client
        self._qolsys_socket: Optional[QolsysSocket] = None
        self._factory: Optional[MqttWrapperFactory] = None
        self._state: Optional[QolsysState] = None
        self._session_token: Optional[str] = None
        self._is_terminated = False
        self._tasks: list[asyncio.Task] = []

        # Create legacy config object for components that still use it
        # TODO: Gradually migrate these to use QolsysConfig directly
        from .qolsys.config import QolsysGatewayConfig
        legacy_args = {
            'panel_host': config.panel.host,
            'panel_port': config.panel.port,
            'panel_mac': config.panel.mac,
            'panel_token': config.panel.token,
            'panel_user_code': config.panel.user_code,
            'panel_unique_id': config.panel.unique_id,
            'panel_device_name': config.panel.device_name,
            'arm_away_exit_delay': config.arming.away_exit_delay,
            'arm_stay_exit_delay': config.arming.stay_exit_delay,
            'arm_away_bypass': config.arming.away_bypass,
            'arm_stay_bypass': config.arming.stay_bypass,
            'arm_type_custom_bypass': config.arming.type_custom_bypass,
            'mqtt_namespace': 'mqtt',  # Not used anymore
            'mqtt_retain': config.mqtt.retain,
            'discovery_topic': config.ha.discovery_prefix,
            'control_topic': config.control_topic,
            'event_topic': config.event_topic,
            'user_control_token': config.user_control_token,
            'ha_check_user_code': config.ha.check_user_code,
            'ha_user_code': config.ha.user_code,
            'code_arm_required': config.ha.code_arm_required,
            'code_disarm_required': config.ha.code_disarm_required,
            'code_trigger_required': config.ha.code_trigger_required,
            'default_trigger_command': config.trigger.default_command,
            'default_sensor_device_class': config.sensor.default_device_class,
            'enable_static_sensors_by_default': config.sensor.enable_static_by_default,
        }
        self._legacy_config = QolsysGatewayConfig(legacy_args, check=False)

    async def initialize(self) -> None:
        """Initialize the gateway and start listening to panel."""
        LOGGER.info('Initializing gateway')
        self._is_terminated = False

        # Generate session token for MQTT control authentication
        self._session_token = str(uuid.uuid4())
        LOGGER.debug(f'Generated session token: {self._session_token}')

        # Create MQTT wrapper factory for publishing discovery/state
        self._factory = MqttWrapperFactory(
            mqtt_publish=self._mqtt_publish_wrapper,
            cfg=self._legacy_config,
            mqtt_plugin_cfg={
                'birth_topic': self._config.mqtt.birth_topic,
                'birth_payload': self._config.mqtt.birth_payload,
            },
            session_token=self._session_token,
        )

        # Create state object
        self._state = QolsysState()

        # Set initial state as unavailable
        # noinspection PyBroadException
        try:
            self._factory.wrap(self._state).set_unavailable()
        except Exception:
            LOGGER.exception('Error setting state unavailable; continuing')

        # Create MQTT updater (observes state changes and publishes to MQTT)
        MqttUpdater(
            state=self._state,
            factory=self._factory
        )

        # Create MQTT event listener (panel → MQTT → internal processing)
        event_listener = MqttQolsysEventListener(
            mqtt_client=self._mqtt_client,
            topic=self._config.event_topic,
            callback=self.mqtt_event_callback,
        )
        await event_listener.start()

        # Create MQTT control listener (HA → MQTT → panel commands)
        control_listener = MqttQolsysControlListener(
            mqtt_client=self._mqtt_client,
            topic=self._config.control_topic,
            callback=self.mqtt_control_callback,
        )
        await control_listener.start()

        # Create Qolsys socket for panel communication
        self._qolsys_socket = QolsysSocket(
            hostname=self._config.panel.host,
            port=self._config.panel.port,
            token=self._config.panel.token,
            callback=self.qolsys_event_callback,
            connected_callback=self.qolsys_connected_callback,
            disconnected_callback=self.qolsys_disconnected_callback,
        )

        # Start panel tasks
        listen_task = asyncio.create_task(
            self._qolsys_socket.listen(),
            name="qolsys_listen"
        )
        keepalive_task = asyncio.create_task(
            self._qolsys_socket.keep_alive(),
            name="qolsys_keepalive"
        )

        self._tasks.extend([listen_task, keepalive_task])

        LOGGER.info('Gateway initialized and started')

    async def terminate(self) -> None:
        """Terminate the gateway and clean up resources."""
        LOGGER.info('Terminating gateway')

        self._is_terminated = True

        # Cancel all tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # Set everything unavailable in MQTT
        if self._state and self._factory:
            self._factory.wrap(self._state).set_unavailable()

            for partition in self._state.partitions:
                for sensor in partition.sensors:
                    # noinspection PyBroadException
                    try:
                        self._factory.wrap(sensor).set_unavailable()
                    except Exception:
                        LOGGER.exception(
                            f"Error setting sensor '{sensor.id}' "
                            f"({sensor.name}) unavailable"
                        )

                # noinspection PyBroadException
                try:
                    self._factory.wrap(partition).set_unavailable()
                except Exception:
                    LOGGER.exception(
                        f"Error setting partition '{partition.id}' "
                        f"({partition.name}) unavailable"
                    )

        LOGGER.info('Gateway terminated')

    async def run(self) -> None:
        """Run the gateway (called from main event loop)."""
        await self.initialize()

        # This will keep running until tasks are cancelled
        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            LOGGER.info("Gateway tasks cancelled")
            raise

    async def _mqtt_publish_wrapper(self, topic: str, payload: str, **kwargs) -> None:
        """Wrapper for MQTT publish to match AppDaemon signature.

        Args:
            topic: MQTT topic
            payload: Message payload
            **kwargs: Additional arguments (namespace, retain, etc.)
        """
        # Extract relevant parameters
        retain = kwargs.get('retain', self._config.mqtt.retain)
        qos = kwargs.get('qos', self._config.mqtt.qos)

        # Ignore 'namespace' parameter (AppDaemon-specific)

        await self._mqtt_client.publish(
            topic=topic,
            payload=payload,
            retain=retain,
            qos=qos,
        )

    async def qolsys_connected_callback(self) -> None:
        """Callback when connected to panel."""
        LOGGER.debug('Panel connected')
        self._factory.wrap(self._state).configure()

    async def qolsys_disconnected_callback(self) -> None:
        """Callback when disconnected from panel."""
        if self._is_terminated:
            return

        LOGGER.debug('Panel disconnected')
        self._factory.wrap(self._state).set_unavailable()

    async def qolsys_event_callback(self, event: QolsysEvent) -> None:
        """Callback for events from panel.

        Publishes events to MQTT for other listeners to process.

        Args:
            event: Event from panel
        """
        LOGGER.debug(f'Panel event: {event}')

        # Publish to MQTT event topic
        await self._mqtt_client.publish(
            topic=self._config.event_topic,
            payload=event.raw_str,
        )

    async def mqtt_event_callback(self, event: QolsysEvent) -> None:
        """Callback for events from MQTT (after being published by qolsys_event_callback).

        Updates internal state based on panel events.

        Args:
            event: Event from MQTT
        """
        LOGGER.debug(f'MQTT event: {event}')

        if isinstance(event, QolsysEventInfoSummary):
            self._state.update(event)

        elif isinstance(event, QolsysEventInfoSecureArm):
            LOGGER.debug(
                f'INFO SecureArm partition_id={event.partition_id} '
                f'value={event.value}'
            )

            partition = self._state.partition(event.partition_id)
            if partition is None:
                LOGGER.warning(f'Partition {event.partition_id} not found')
                return

            partition.secure_arm = event.value

        elif isinstance(event, QolsysEventZoneEventActive):
            LOGGER.debug(f'ACTIVE zone={event.zone}')

            if event.zone.status.lower() == 'open':
                self._state.zone_open(event.zone.id)
            else:
                self._state.zone_closed(event.zone.id)

        elif isinstance(event, QolsysEventZoneEventUpdate):
            LOGGER.debug(f'UPDATE zone={event.zone}')

            # This event provides a full zone object, so we need to provide
            # it our current partition object
            partition = self._state.partition(event.zone.partition_id)
            if partition is None:
                LOGGER.warning(f'Partition {event.zone.partition_id} not found')
                return
            event.zone.partition = partition

            self._state.zone_update(event.zone)

        elif isinstance(event, QolsysEventZoneEventAdd):
            LOGGER.debug(f'ADD zone={event.zone}')

            # This event provides a full zone object, so we need to provide
            # it our current partition object
            partition = self._state.partition(event.zone.partition_id)
            if partition is None:
                LOGGER.warning(f'Partition {event.zone.partition_id} not found')
                return
            event.zone.partition = partition

            self._state.zone_add(event.zone)

        elif isinstance(event, QolsysEventArming):
            LOGGER.debug(
                f'ARMING partition_id={event.partition_id} '
                f'status={event.arming_type}'
            )

            partition = self._state.partition(event.partition_id)
            if partition is None:
                LOGGER.warning(f'Partition {event.partition_id} not found')
                return

            partition.status = event.arming_type

        elif isinstance(event, QolsysEventAlarm):
            LOGGER.debug(f'ALARM partition_id={event.partition_id}')

            partition = self._state.partition(event.partition_id)
            if partition is None:
                LOGGER.warning(f'Partition {event.partition_id} not found')
                return

            partition.triggered(alarm_type=event.alarm_type)

        elif isinstance(event, QolsysEventError):
            LOGGER.debug(f'ERROR partition_id={event.partition_id}')

            partition = self._state.partition(event.partition_id)
            if partition is None:
                LOGGER.warning(f'Partition {event.partition_id} not found')
                return

            partition.errored(
                error_type=event.error_type,
                error_description=event.description
            )

        else:
            LOGGER.info(f'UNCAUGHT event {event}; ignored')

    async def mqtt_control_callback(self, control: QolsysControl) -> None:
        """Callback for control messages from MQTT (Home Assistant).

        Args:
            control: Control command from HA
        """
        # Validate session token
        if control.session_token != self._session_token and (
                self._config.user_control_token is None or
                control.session_token != self._config.user_control_token):
            LOGGER.error(f'Invalid session token for {control}')
            return

        # Configure control with config/state if needed
        if control.requires_config:
            control.configure(self._legacy_config, self._state)

        # Check control validity (user codes, etc.)
        try:
            control.check()
        except (MissingUserCodeException, InvalidUserCodeException) as e:
            LOGGER.error(f'{e} for control event {control}')
            return

        # Get action to send to panel
        action = control.action
        if action is None:
            LOGGER.info(f'Action missing for control event {control}')
            return

        # Send action to panel
        await self._qolsys_socket.send(action)