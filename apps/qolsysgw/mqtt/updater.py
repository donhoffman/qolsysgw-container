import asyncio
import json
import logging
import posixpath
from typing import Callable

from apps.qolsysgw.mqtt.exceptions import (
    UnknownDeviceClassException,
    UnknownMqttWrapperException,
)
from apps.qolsysgw.mqtt.utils import normalize_name_to_id

from apps.qolsysgw.qolsys.config import QolsysGatewayConfig
from apps.qolsysgw.qolsys.partition import QolsysPartition
from apps.qolsysgw.qolsys.sensors import (
    QolsysSensor,
    QolsysSensorAuxiliaryPendant,
    QolsysSensorBluetooth,
    QolsysSensorCODetector,
    QolsysSensorDoorWindow,
    QolsysSensorDoorbell,
    QolsysSensorFreeze,
    QolsysSensorGlassBreak,
    QolsysSensorHeat,
    QolsysSensorKeyFob,
    QolsysSensorKeypad,
    QolsysSensorMotion,
    QolsysSensorShock,
    QolsysSensorSiren,
    QolsysSensorSmokeDetector,
    QolsysSensorTakeoverModule,
    QolsysSensorTemperature,
    QolsysSensorTilt,
    QolsysSensorTranslator,
    QolsysSensorWater,
    _QolsysSensorWithoutUpdates,
)
from apps.qolsysgw.qolsys.state import QolsysState
from apps.qolsysgw.qolsys.utils import default_logger_callback, find_subclass

LOGGER = logging.getLogger(__name__)


class MqttUpdater(object):
    def __init__(self, state: QolsysState, factory: 'MqttWrapperFactory',
                 callback: Callable = None, logger=None):
        self._factory = factory
        self._callback = callback or default_logger_callback
        self._logger = logger or LOGGER

        state.register(self, callback=self._state_update)

    def _state_update(self, state: QolsysState, change, prev_value=None, new_value=None):
        self._logger.debug(f"Received update from state for CHANGE={change}")

        if change == QolsysState.NOTIFY_UPDATE_PARTITIONS:
            # The partitions have been updated, make sure we are registered for
            # all those partitions
            for partition in state.partitions:
                partition.register(self, callback=self._partition_update)
                asyncio.create_task(self._factory.wrap(partition).configure())
                # The partition might already have sensors on it, so register
                # for each sensor individually too
                for sensor in partition.sensors:
                    sensor.register(self, callback=self._sensor_update)
                    asyncio.create_task(self._factory.wrap(sensor).configure(partition=partition))
        elif change == QolsysState.NOTIFY_UPDATE_ERROR:
            # An error has happened on qolsysgw, so we want to update the
            # state sensor
            wrapped_state = self._factory.wrap(state)
            asyncio.create_task(wrapped_state.update_state())
            asyncio.create_task(wrapped_state.update_attributes())

    def _partition_update(self, partition: QolsysPartition, change, prev_value=None, new_value=None):
        self._logger.debug(f"Received update from partition "
                           f"'{partition.name}' for CHANGE={change}, from "
                           f"prev_value={prev_value} to new_value={new_value}")

        if change == QolsysPartition.NOTIFY_ADD_SENSOR:
            sensor = new_value
            sensor.register(self, callback=self._sensor_update)
            asyncio.create_task(self._factory.wrap(sensor).configure(partition=partition))
        elif change == QolsysPartition.NOTIFY_UPDATE_STATUS:
            asyncio.create_task(self._factory.wrap(partition).update_state())
        elif change == QolsysPartition.NOTIFY_UPDATE_SECURE_ARM:
            asyncio.create_task(self._factory.wrap(partition).configure())
        elif change == QolsysPartition.NOTIFY_UPDATE_ALARM_TYPE or \
                change == QolsysPartition.NOTIFY_UPDATE_ATTRIBUTES:
            asyncio.create_task(self._factory.wrap(partition).update_attributes())

    def _sensor_update(self, sensor: QolsysSensor, change, prev_value=None, new_value=None):
        self._logger.debug(f"Received update from sensor '{sensor.name}' for "
                           f"CHANGE={change}, from prev_value={prev_value} to "
                           f"new_value={new_value}")

        if change == QolsysSensor.NOTIFY_UPDATE_STATUS:
            asyncio.create_task(self._factory.wrap(sensor).update_state())
        elif change == QolsysSensor.NOTIFY_UPDATE_ATTRIBUTES:
            asyncio.create_task(self._factory.wrap(sensor).update_attributes())


class MqttWrapper(object):

    def __init__(self, mqtt_publish: Callable, cfg: QolsysGatewayConfig,
                 availability_topic: str,
                 availability_payload_online: str,
                 availability_payload_offline: str,
                 session_token: str) -> None:
        self._mqtt_publish = mqtt_publish
        self._cfg = cfg

        self._availability_topic = availability_topic
        self._availability_payload_online = availability_payload_online
        self._availability_payload_offline = availability_payload_offline

        self._session_token = session_token

        # Retain is enabled for all messages since we have proper LWT support
        self._mqtt_retain = self._cfg.mqtt_retain

    @property
    def name(self) -> str:
        """Return entity name. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement 'name' property")

    @property
    def topic_path(self) -> str:
        """Return MQTT topic path. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement 'topic_path' property")

    def configure_payload(self, **kwargs) -> dict:
        """Return configuration payload. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement 'configure_payload' method")

    @property
    def entity_id(self):
        return normalize_name_to_id(self.name)

    @property
    def config_topic(self):
        return posixpath.join(self._cfg.discovery_topic,
                              self.topic_path, 'config')

    @property
    def state_topic(self):
        return posixpath.join(self._cfg.discovery_topic,
                              self.topic_path, 'state')

    @property
    def attributes_topic(self):
        return posixpath.join(self._cfg.discovery_topic,
                              self.topic_path, 'attributes')

    @property
    def availability_topic(self):
        return posixpath.join(self._cfg.discovery_topic,
                              self.topic_path, 'availability')

    @property
    def device_availability_topic(self):
        return posixpath.join(self._cfg.discovery_topic,
                              'alarm_control_panel',
                              self._cfg.panel_unique_id,
                              'availability')

    @property
    def payload_available(self):
        return 'online'

    @property
    def payload_unavailable(self):
        return 'offline'

    @property
    def device_payload(self):
        payload = {
            'name': self._cfg.panel_device_name,
            'identifiers': [
                self._cfg.panel_unique_id,
            ],
            'manufacturer': 'Qolsys',
            'model': 'IQ Panel 2+',
        }

        # If we have the mac address, this will allow to link the device
        # to other related elements in home assistant
        if self._cfg.panel_mac:
            payload['connections'] = [
                ['mac', self._cfg.panel_mac],
            ]

        return payload

    @property
    def configure_availability(self):
        """Return availability configuration for MQTT discovery.

        All entities reference the panel availability topic (with LWT),
        which ensures they go unavailable if the gateway crashes or disconnects.
        """
        return [
            {
                'topic': self._availability_topic,
                'payload_available': self._availability_payload_online,
                'payload_not_available': self._availability_payload_offline,
            },
        ]

    async def configure(self, **kwargs):
        await self._mqtt_publish(
            namespace=self._cfg.mqtt_namespace,
            topic=self.config_topic,
            retain=True,
            payload=json.dumps(self.configure_payload(**kwargs)),
        )

        await self.set_available()
        await self.update_state()
        await self.update_attributes()

    async def update_attributes(self):
        pass

    async def update_state(self):
        pass

    async def set_available(self):
        await self._mqtt_publish(
            namespace=self._cfg.mqtt_namespace,
            topic=self.availability_topic,
            retain=self._mqtt_retain,
            payload=self.payload_available,
        )

    async def set_unavailable(self):
        await self._mqtt_publish(
            namespace=self._cfg.mqtt_namespace,
            topic=self.availability_topic,
            retain=True,
            payload=self.payload_unavailable,
        )


class MqttWrapperQolsysState(MqttWrapper):
    def __init__(self, state: QolsysState, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._state = state

    @property
    def name(self):
        return self._cfg.panel_unique_id

    @property
    def entity_id(self):
        return f'{self.name}_last_error'

    @property
    def availability_topic(self):
        return self.device_availability_topic

    @property
    def topic_path(self):
        return posixpath.join(
            'sensor',
            self.entity_id,
        )

    def configure_payload(self, **_kwargs):
        payload = {'name': 'Last Error', 'device_class': 'timestamp', 'state_topic': self.state_topic,
                   'availability_mode': 'all', 'availability': self.configure_availability,
                   'json_attributes_topic': self.attributes_topic,
                   'unique_id': f"{self._cfg.panel_unique_id}_last_error", 'device': self.device_payload}

        return payload

    async def update_attributes(self):
        if self._state.last_exception:
            exc_type = type(self._state.last_exception).__name__
            exc_desc = str(self._state.last_exception)
        else:
            exc_type = None
            exc_desc = None

        await self._mqtt_publish(
            namespace=self._cfg.mqtt_namespace,
            topic=self.attributes_topic,
            retain=self._mqtt_retain,
            payload=json.dumps({
                'type': exc_type,
                'desc': exc_desc,
            }),
        )

    async def update_state(self):
        await self._mqtt_publish(
            namespace=self._cfg.mqtt_namespace,
            topic=self.state_topic,
            retain=self._mqtt_retain,
            payload=(self._state.last_exception.at
                     if self._state.last_exception
                     else None),
        )


class MqttWrapperQolsysPartition(MqttWrapper):

    QOLSYS_TO_HA_STATUS = {
        'DISARM': 'disarmed',
        'ARM_STAY': 'armed_home',
        'ARM_AWAY': 'armed_away',
        # 'ARM_NIGHT': 'armed_night',
        # '': 'armed_vacation',
        # '': 'armed_custom_bypass',
        'ENTRY_DELAY': 'pending',
        'ALARM': 'triggered',
        'EXIT_DELAY': 'arming',
        'ARM-AWAY-EXIT-DELAY': 'arming',
        'ARM-STAY-EXIT-DELAY': 'arming',
    }

    def __init__(self, partition: QolsysPartition, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._partition = partition

    async def set_available(self):
        """Partitions use panel availability topic - no individual publishing needed."""
        pass

    async def set_unavailable(self):
        """Partitions use panel availability topic - no individual publishing needed."""
        pass

    @property
    def name(self):
        return self._partition.name

    @property
    def ha_status(self):
        status = self.QOLSYS_TO_HA_STATUS.get(self._partition.status)
        if not status:
            raise ValueError('We need to put a better error here, but '
                             'we found an unsupported status: '
                             f"'{self._partition.status}'")
        return status

    @property
    def topic_path(self):
        return posixpath.join(
            'alarm_control_panel',
            self._cfg.panel_unique_id,
            self.entity_id,
        )

    def configure_payload(self, **_kwargs):
        command_template = {
            'partition_id': str(self._partition.id),
            'action': '{{ action }}',
            'session_token': self._session_token,
        }
        if (self._cfg.code_arm_required or self._cfg.code_disarm_required) and\
                not self._cfg.ha_check_user_code:
            # It is the only situation where we actually need to transmit
            # the code regularly through mqtt. In any other situation, we can
            # use the session token for comparison, which will allow to avoid
            # sharing the code in MQTT after initialization
            command_template['code'] = '{{ code }}'

        secure_arm = (self._partition.secure_arm and
                      not self._cfg.panel_user_code)

        payload = {'name': self.name, 'state_topic': self.state_topic,
                   'code_arm_required': self._cfg.code_arm_required or secure_arm,
                   'code_disarm_required': self._cfg.code_disarm_required,
                   'code_trigger_required': self._cfg.code_trigger_required or secure_arm,
                   'command_topic': self._cfg.control_topic, 'command_template': json.dumps(command_template),
                   'availability_mode': 'all', 'availability': self.configure_availability,
                   'json_attributes_topic': self.attributes_topic,
                   'unique_id': f"{self._cfg.panel_unique_id}_p{self._partition.id}", 'device': self.device_payload}

        # As we have a unique ID for the panel, we can set up a unique ID for
        # the partition, and create a device to link all of our partitions
        # together; this will also allow to interact with the partition in
        # the UI, change its name, assign it to areas, etc.

        if self._cfg.default_trigger_command:
            payload['payload_trigger'] = self._cfg.default_trigger_command

        if self._cfg.code_arm_required or self._cfg.code_disarm_required:
            code = self._cfg.ha_user_code or self._cfg.panel_user_code
            if self._cfg.ha_check_user_code:
                payload['code'] = code
            elif code is None or code.isdigit():
                payload['code'] = 'REMOTE_CODE'
            else:
                payload['code'] = 'REMOTE_CODE_TEXT'

        return payload

    async def update_attributes(self):
        await self._mqtt_publish(
            namespace=self._cfg.mqtt_namespace,
            topic=self.attributes_topic,
            retain=self._mqtt_retain,
            payload=json.dumps({
                'secure_arm': self._partition.secure_arm,
                'alarm_type': self._partition.alarm_type,
                'last_error_type': self._partition.last_error_type,
                'last_error_desc': self._partition.last_error_desc,
                'last_error_at': self._partition.last_error_at,
                'disarm_failed': self._partition.disarm_failed,
            }),
        )

    async def update_state(self):
        await self._mqtt_publish(
            namespace=self._cfg.mqtt_namespace,
            topic=self.state_topic,
            retain=self._mqtt_retain,
            payload=self.ha_status,
        )


class MqttWrapperQolsysSensor(MqttWrapper):

    PAYLOAD_ON = 'Open'
    PAYLOAD_OFF = 'Closed'

    QOLSYS_TO_HA_DEVICE_CLASS = {
        QolsysSensorAuxiliaryPendant: 'safety',
        QolsysSensorBluetooth: 'presence',
        QolsysSensorCODetector: 'gas',
        QolsysSensorDoorWindow: 'door',
        QolsysSensorDoorbell: 'sound',
        QolsysSensorFreeze: 'cold',
        QolsysSensorGlassBreak: 'vibration',
        QolsysSensorHeat: 'heat',
        QolsysSensorKeyFob: 'safety',
        QolsysSensorKeypad: 'safety',
        QolsysSensorMotion: 'motion',
        QolsysSensorShock: 'vibration',
        QolsysSensorSiren: 'safety',
        QolsysSensorSmokeDetector: 'smoke',
        QolsysSensorTakeoverModule: 'safety',
        QolsysSensorTemperature: 'heat',
        QolsysSensorTilt: 'garage_door',
        QolsysSensorTranslator: 'safety',
        QolsysSensorWater: 'moisture',
    }

    def __init__(self, sensor: QolsysSensor, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._sensor = sensor

    async def set_available(self):
        """Sensors use panel availability topic - no individual publishing needed."""
        pass

    async def set_unavailable(self):
        """Sensors use panel availability topic - no individual publishing needed."""
        pass

    @property
    def name(self):
        return self._sensor.name

    @property
    def ha_device_class(self):
        for base in type(self._sensor).mro():
            device_class = self.QOLSYS_TO_HA_DEVICE_CLASS.get(base)
            if device_class:
                return device_class

        error_perm_msg = 'Unable to find a device class to map for ' \
                         f"sensor type {type(self._sensor).__name__}"
        if self._cfg.default_sensor_device_class:
            LOGGER.warning(f"{error_perm_msg}, defaulting to "
                           f"'{self._cfg.default_sensor_device_class}' "
                           "device class.")
            return self._cfg.default_sensor_device_class
        else:
            raise UnknownDeviceClassException(error_perm_msg)

    @property
    def topic_path(self):
        return posixpath.join(
            'binary_sensor',
            self.entity_id,
        )

    def configure_payload(self, partition: QolsysPartition = None, **_kwargs):
        payload = {'name': self.name, 'device_class': self.ha_device_class, 'state_topic': self.state_topic,
                   'payload_on': self.PAYLOAD_ON, 'payload_off': self.PAYLOAD_OFF, 'availability_mode': 'all',
                   'availability': self.configure_availability, 'json_attributes_topic': self.attributes_topic,
                   'enabled_by_default': (
                       self._cfg.enable_static_sensors_by_default or
                       not isinstance(self._sensor, _QolsysSensorWithoutUpdates)
                   ), 'unique_id': f"{self._cfg.panel_unique_id}_"
                                   f"s{normalize_name_to_id(self._sensor.unique_id)}", 'device': self.device_payload}

        # As we have a unique ID for the panel, we can set up a unique ID for
        # the partition, and create a device to link all of our partitions
        # together; this will also allow to interact with the partition in
        # the UI, change its name, assign it to areas, etc.

        return payload

    async def update_attributes(self):
        attributes = {
            k: getattr(self._sensor, k)
            for k in self._sensor.ATTRIBUTES
        }

        await self._mqtt_publish(
            namespace=self._cfg.mqtt_namespace,
            topic=self.attributes_topic,
            retain=self._mqtt_retain,
            payload=json.dumps(attributes),
        )

    async def update_state(self):
        await self._mqtt_publish(
            namespace=self._cfg.mqtt_namespace,
            topic=self.state_topic,
            retain=self._mqtt_retain,
            payload=self._sensor.status,
        )


class MqttWrapperFactory(object):

    __WRAPPERCLASSES_CACHE = {}

    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs

    def wrap(self, obj):
        for base in type(obj).mro():
            klass = find_subclass(MqttWrapper, base.__name__,
                                  cache=self.__WRAPPERCLASSES_CACHE,
                                  normalize=False)
            if klass:
                return klass(obj, *self._args, **self._kwargs)

        raise UnknownMqttWrapperException(
            f'Unable to wrap object type {type(obj).__name__}'
        )
