import logging

from apps.qolsysgw.mqtt.exceptions import MqttException
from apps.qolsysgw.qolsys.events import QolsysEventInfoSummary
from apps.qolsysgw.qolsys.exceptions import QolsysException
from apps.qolsysgw.qolsys.exceptions import QolsysSyncException
from apps.qolsysgw.qolsys.observable import QolsysObservable


LOGGER = logging.getLogger(__name__)


class QolsysState(QolsysObservable):
    NOTIFY_UPDATE_PARTITIONS = 'update_partitions'
    NOTIFY_UPDATE_ERROR = 'update_error'

    def __init__(self, event: QolsysEventInfoSummary = None):
        super().__init__()

        self._last_exception = None

        self._partitions = {}
        if event:
            self.update(event)

        QolsysException.STATE = self
        MqttException.STATE = self

    @property
    def last_exception(self):
        return self._last_exception

    @last_exception.setter
    def last_exception(self, value):
        prev_value = self._last_exception
        self._last_exception = value

        self.notify(change=self.NOTIFY_UPDATE_ERROR,
                    prev_value=prev_value,
                    new_value=value)

    @property
    def partitions(self):
        return self._partitions.values()

    def partition(self, partition_id):
        return self._partitions.get(int(partition_id))

    def update(self, event: QolsysEventInfoSummary):
        prev_partitions = self.partitions

        self._partitions = {}
        for partition in event.partitions:
            self._partitions[int(partition.id)] = partition

        self.notify(change=self.NOTIFY_UPDATE_PARTITIONS,
                    prev_value=prev_partitions,
                    new_value=self.partitions)

    def zone(self, zone_id):
        for partition in self.partitions:
            zone = partition.zone(zone_id)
            if zone is not None:
                return zone
        return None

    def sensor(self, sensor_id):
        for partition in self.partitions:
            sensor = partition.sensor(sensor_id)
            if sensor is not None:
                return sensor
        return None

    def zone_update(self, sensor):
        # Find where the zone is currently at
        current_zone = self.zone(sensor.zone_id)
        if current_zone is None:
            raise QolsysSyncException(
                f'Zone not found for zone update: {sensor}, '
                'gateway state may be out of sync with panel'
            )

        if current_zone.partition_id == sensor.partition_id:
            self._partitions[sensor.partition_id].update_sensor(sensor)
        else:
            self._partitions[current_zone.partition_id].remove_zone(sensor.zone_id)
            self._partitions[sensor.partition_id].add_sensor(sensor)

    def zone_add(self, sensor):
        partition = self._partitions.get(sensor.partition_id)
        if partition is None:
            raise QolsysSyncException(
                f'Partition not found for zone add: {sensor}, '
                'gateway state may be out of sync with panel'
            )

        self._partitions[sensor.partition_id].add_sensor(sensor)

    def zone_open(self, zone_id):
        for partition in self.partitions:
            zone = partition.zone(zone_id)
            if zone is not None:
                zone.open()

    def zone_closed(self, zone_id):
        for partition in self.partitions:
            zone = partition.zone(zone_id)
            if zone is not None:
                zone.closed()
