import json
import unittest

from unittest import mock

import tests.unit.qolsysgw.mqtt.testenv  # noqa: F401

from apps.qolsysgw.mqtt.listener import MqttQolsysControlListener
from apps.qolsysgw.mqtt.listener import MqttQolsysEventListener


# test MqttQolsysEventListener
class TestUnitMqttQolsysEventListener(unittest.IsolatedAsyncioTestCase):

    async def test_unit_event_callback_on_success(self):
        # mock event_callback
        event_callback = mock.AsyncMock()
        # mock MQTT client
        mqtt_client = mock.Mock()
        # create MqttQolsysEventListener
        listener = MqttQolsysEventListener(
            mqtt_client=mqtt_client,
            topic='test_topic',
            callback=event_callback,
        )
        # mock payload
        payload = json.dumps({'event_type': 'test'})
        # call event_callback
        qolsys_event = object()
        with mock.patch('apps.qolsysgw.qolsys.events.QolsysEvent.from_json', return_value=qolsys_event):
            await listener.event_callback('test_topic', payload)
        # assert event_callback was called
        event_callback.assert_called_once_with(qolsys_event)

    async def test_unit_event_callback_on_empty_payload(self):
        # mock event_callback
        event_callback = mock.AsyncMock()
        # mock MQTT client
        mqtt_client = mock.Mock()
        # create MqttQolsysEventListener
        listener = MqttQolsysEventListener(
            mqtt_client=mqtt_client,
            topic='test_topic',
            callback=event_callback,
        )
        # call event_callback with empty payload
        await listener.event_callback('test_topic', '')
        # assert event_callback was not called
        event_callback.assert_not_called()

    async def test_unit_event_callback_on_unhandled_failure(self):
        # mock event_callback
        event_callback = mock.AsyncMock()
        # mock MQTT client
        mqtt_client = mock.Mock()
        # create MqttQolsysEventListener
        listener = MqttQolsysEventListener(
            mqtt_client=mqtt_client,
            topic='test_topic',
            callback=event_callback,
        )
        # mock payload
        payload = json.dumps({'event_type': 'test'})
        # mock QolsysEvent.from_json to raise UnknownQolsysEventException
        from apps.qolsysgw.qolsys.exceptions import UnknownQolsysEventException
        with mock.patch('apps.qolsysgw.qolsys.events.QolsysEvent.from_json', side_effect=UnknownQolsysEventException('test_exception')):
            # call event_callback (should not raise)
            await listener.event_callback('test_topic', payload)
        # assert event_callback was not called (exception was caught)
        event_callback.assert_not_called()


# test MqttQolsysControlListener
class TestUnitMqttQolsysControlListener(unittest.IsolatedAsyncioTestCase):

    async def test_unit_event_callback_on_success(self):
        # mock event_callback
        event_callback = mock.AsyncMock()
        # mock MQTT client
        mqtt_client = mock.Mock()
        # create MqttQolsysControlListener
        listener = MqttQolsysControlListener(
            mqtt_client=mqtt_client,
            topic='test_topic',
            callback=event_callback,
        )
        # mock payload
        payload = json.dumps({'action': 'ARM_AWAY'})
        # call event_callback
        qolsys_control = object()
        with mock.patch('apps.qolsysgw.qolsys.control.QolsysControl.from_json', return_value=qolsys_control):
            await listener.event_callback('test_topic', payload)
        # assert event_callback was called
        event_callback.assert_called_once_with(qolsys_control)

    async def test_unit_event_callback_on_empty_payload(self):
        # mock event_callback
        event_callback = mock.AsyncMock()
        # mock MQTT client
        mqtt_client = mock.Mock()
        # create MqttQolsysControlListener
        listener = MqttQolsysControlListener(
            mqtt_client=mqtt_client,
            topic='test_topic',
            callback=event_callback,
        )
        # call event_callback with empty payload
        await listener.event_callback('test_topic', '')
        # assert event_callback was not called
        event_callback.assert_not_called()

    async def test_unit_event_callback_on_unhandled_failure(self):
        # mock event_callback
        event_callback = mock.AsyncMock()
        # mock MQTT client
        mqtt_client = mock.Mock()
        # create MqttQolsysControlListener
        listener = MqttQolsysControlListener(
            mqtt_client=mqtt_client,
            topic='test_topic',
            callback=event_callback,
        )
        # mock payload
        payload = json.dumps({'action': 'ARM_AWAY'})
        # mock QolsysControl.from_json to raise UnknownQolsysControlException
        from apps.qolsysgw.qolsys.exceptions import UnknownQolsysControlException
        with mock.patch('apps.qolsysgw.qolsys.control.QolsysControl.from_json', side_effect=UnknownQolsysControlException('test_exception')):
            # call event_callback (should not raise)
            await listener.event_callback('test_topic', payload)
        # assert event_callback was not called (exception was caught)
        event_callback.assert_not_called()


if __name__ == '__main__':
    unittest.main()
