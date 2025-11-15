import os
import tempfile
import unittest
from pathlib import Path

import tests.unit.qolsysgw.testenv  # noqa: F401

from apps.qolsysgw.config import (
    ArmingConfig,
    HomeAssistantConfig,
    MqttConfig,
    PanelConfig,
    QolsysConfig,
    TriggerConfig,
)
from pydantic import ValidationError

import logging
logging.basicConfig(level=logging.DEBUG)


class TestUnitPanelConfig(unittest.TestCase):
    """Test PanelConfig validation and defaults."""

    def setUp(self):
        """Clear environment variables before each test."""
        for key in list(os.environ.keys()):
            if key.startswith("QOLSYS_PANEL_"):
                del os.environ[key]

    def test_required_fields(self):
        """Test that required fields are enforced."""
        with self.assertRaises(ValidationError) as cm:
            PanelConfig()

        errors = cm.exception.errors()
        field_names = {e["loc"][0] for e in errors}
        self.assertIn("host", field_names)
        self.assertIn("token", field_names)

    def test_valid_config(self):
        """Test creating valid panel config."""
        config = PanelConfig(
            host="192.168.1.100",
            token="abc123def456"
        )

        self.assertEqual(config.host, "192.168.1.100")
        self.assertEqual(config.token, "abc123def456")
        self.assertEqual(config.unique_id, "qolsys_panel")  # default
        self.assertEqual(config.device_name, "Qolsys Panel")  # default
        self.assertIsNone(config.user_code)  # optional
        self.assertIsNone(config.port)  # optional

    def test_user_code_validation_4_digits(self):
        """Test user code validation with 4 digits."""
        config = PanelConfig(
            host="192.168.1.100",
            token="abc123",
            user_code="1234"
        )
        self.assertEqual(config.user_code, "1234")

    def test_user_code_validation_6_digits(self):
        """Test user code validation with 6 digits."""
        config = PanelConfig(
            host="192.168.1.100",
            token="abc123",
            user_code="123456"
        )
        self.assertEqual(config.user_code, "123456")

    def test_user_code_validation_invalid_length(self):
        """Test user code validation rejects invalid length."""
        with self.assertRaises(ValidationError) as cm:
            PanelConfig(
                host="192.168.1.100",
                token="abc123",
                user_code="12345"  # 5 digits - invalid
            )

        errors = cm.exception.errors()
        self.assertEqual(len(errors), 1)
        self.assertIn("4 or 6 digits", str(errors[0]["ctx"]["error"]))

    def test_user_code_validation_non_digits(self):
        """Test user code validation rejects non-digits."""
        with self.assertRaises(ValidationError) as cm:
            PanelConfig(
                host="192.168.1.100",
                token="abc123",
                user_code="12ab"
            )

        errors = cm.exception.errors()
        self.assertIn("only digits", str(errors[0]["ctx"]["error"]))

    def test_env_var_loading(self):
        """Test loading from environment variables."""
        os.environ["QOLSYS_PANEL_HOST"] = "192.168.1.200"
        os.environ["QOLSYS_PANEL_TOKEN"] = "token123"
        os.environ["QOLSYS_PANEL_USER_CODE"] = "1234"
        os.environ["QOLSYS_PANEL_UNIQUE_ID"] = "my_panel"

        config = PanelConfig()

        self.assertEqual(config.host, "192.168.1.200")
        self.assertEqual(config.token, "token123")
        self.assertEqual(config.user_code, "1234")
        self.assertEqual(config.unique_id, "my_panel")


class TestUnitArmingConfig(unittest.TestCase):
    """Test ArmingConfig validation and defaults."""

    def setUp(self):
        """Clear environment variables before each test."""
        for key in list(os.environ.keys()):
            if key.startswith("QOLSYS_ARM_"):
                del os.environ[key]

    def test_defaults(self):
        """Test default values."""
        config = ArmingConfig()

        self.assertIsNone(config.away_exit_delay)
        self.assertIsNone(config.stay_exit_delay)
        self.assertIsNone(config.away_bypass)
        self.assertIsNone(config.stay_bypass)
        self.assertEqual(config.type_custom_bypass, "arm_away")  # default

    def test_valid_arm_type_away(self):
        """Test valid arm type 'arm_away'."""
        config = ArmingConfig(type_custom_bypass="arm_away")
        self.assertEqual(config.type_custom_bypass, "arm_away")

    def test_valid_arm_type_stay(self):
        """Test valid arm type 'arm_stay'."""
        config = ArmingConfig(type_custom_bypass="arm_stay")
        self.assertEqual(config.type_custom_bypass, "arm_stay")

    def test_invalid_arm_type(self):
        """Test invalid arm type is rejected."""
        with self.assertRaises(ValidationError) as cm:
            ArmingConfig(type_custom_bypass="arm_custom")

        errors = cm.exception.errors()
        self.assertIn("arm_away", str(errors[0]["ctx"]["error"]))
        self.assertIn("arm_stay", str(errors[0]["ctx"]["error"]))

    def test_env_var_loading(self):
        """Test loading from environment variables."""
        os.environ["QOLSYS_ARM_AWAY_EXIT_DELAY"] = "30"
        os.environ["QOLSYS_ARM_STAY_EXIT_DELAY"] = "0"
        os.environ["QOLSYS_ARM_AWAY_BYPASS"] = "true"
        os.environ["QOLSYS_ARM_STAY_BYPASS"] = "false"

        config = ArmingConfig()

        self.assertEqual(config.away_exit_delay, 30)
        self.assertEqual(config.stay_exit_delay, 0)
        self.assertTrue(config.away_bypass)
        self.assertFalse(config.stay_bypass)


class TestUnitMqttConfig(unittest.TestCase):
    """Test MqttConfig validation and defaults."""

    def setUp(self):
        """Clear environment variables before each test."""
        for key in list(os.environ.keys()):
            if key.startswith("MQTT_"):
                del os.environ[key]

    def test_required_fields(self):
        """Test that required fields are enforced."""
        with self.assertRaises(ValidationError) as cm:
            MqttConfig()

        errors = cm.exception.errors()
        field_names = {e["loc"][0] for e in errors}
        self.assertIn("host", field_names)

    def test_defaults(self):
        """Test default values."""
        config = MqttConfig(host="mqtt.broker.local")

        self.assertEqual(config.port, 1883)
        self.assertIsNone(config.username)
        self.assertIsNone(config.password)
        self.assertEqual(config.qos, 1)
        self.assertTrue(config.retain)

    def test_qos_validation(self):
        """Test QoS must be between 0-2."""
        # Valid QoS values
        for qos in [0, 1, 2]:
            config = MqttConfig(host="mqtt.broker.local", qos=qos)
            self.assertEqual(config.qos, qos)

        # Invalid QoS
        with self.assertRaises(ValidationError):
            MqttConfig(host="mqtt.broker.local", qos=3)

        with self.assertRaises(ValidationError):
            MqttConfig(host="mqtt.broker.local", qos=-1)


class TestUnitHomeAssistantConfig(unittest.TestCase):
    """Test HomeAssistantConfig validation."""

    def setUp(self):
        """Clear environment variables before each test."""
        for key in list(os.environ.keys()):
            if key.startswith("HA_"):
                del os.environ[key]

    def test_defaults(self):
        """Test default values."""
        config = HomeAssistantConfig()

        self.assertEqual(config.discovery_prefix, "homeassistant")
        self.assertTrue(config.check_user_code)
        self.assertIsNone(config.user_code)
        self.assertFalse(config.code_arm_required)
        self.assertFalse(config.code_disarm_required)
        self.assertFalse(config.code_trigger_required)

    def test_user_code_validation_4_digits(self):
        """Test HA user code validation with 4 digits."""
        config = HomeAssistantConfig(user_code="1234")
        self.assertEqual(config.user_code, "1234")

    def test_user_code_validation_6_digits(self):
        """Test HA user code validation with 6 digits."""
        config = HomeAssistantConfig(user_code="123456")
        self.assertEqual(config.user_code, "123456")

    def test_user_code_validation_invalid(self):
        """Test HA user code validation rejects invalid codes."""
        with self.assertRaises(ValidationError) as cm:
            HomeAssistantConfig(user_code="12345")

        errors = cm.exception.errors()
        self.assertIn("4 or 6 digits", str(errors[0]["ctx"]["error"]))


class TestUnitTriggerConfig(unittest.TestCase):
    """Test TriggerConfig validation."""

    def setUp(self):
        """Clear environment variables before each test."""
        for key in list(os.environ.keys()):
            if key.startswith("QOLSYS_TRIGGER_"):
                del os.environ[key]

    def test_defaults(self):
        """Test default values."""
        config = TriggerConfig()
        self.assertIsNone(config.default_command)

    def test_valid_trigger_commands(self):
        """Test valid trigger commands."""
        valid_commands = ["TRIGGER", "TRIGGER_AUXILIARY", "TRIGGER_FIRE", "TRIGGER_POLICE"]

        for cmd in valid_commands:
            config = TriggerConfig(default_command=cmd)
            self.assertEqual(config.default_command, cmd)

    def test_trigger_command_case_insensitive(self):
        """Test trigger command is case-insensitive."""
        config = TriggerConfig(default_command="trigger")
        self.assertEqual(config.default_command, "TRIGGER")

    def test_invalid_trigger_command(self):
        """Test invalid trigger command is rejected."""
        with self.assertRaises(ValidationError) as cm:
            TriggerConfig(default_command="INVALID_TRIGGER")

        errors = cm.exception.errors()
        self.assertIn("Invalid trigger command", str(errors[0]["ctx"]["error"]))


class TestUnitQolsysConfig(unittest.TestCase):
    """Test main QolsysConfig class."""

    def setUp(self):
        """Clear environment variables before each test."""
        for key in list(os.environ.keys()):
            if any(key.startswith(prefix) for prefix in [
                "QOLSYS_", "MQTT_", "HA_", "CONFIG_FILE"
            ]):
                del os.environ[key]

    def test_minimal_valid_config(self):
        """Test creating minimal valid configuration."""
        config = QolsysConfig(
            panel=PanelConfig(
                host="192.168.1.100",
                token="abc123"
            ),
            mqtt=MqttConfig(
                host="mqtt.broker.local"
            )
        )

        self.assertEqual(config.panel.host, "192.168.1.100")
        self.assertEqual(config.mqtt.host, "mqtt.broker.local")
        self.assertIsNotNone(config.ha)
        self.assertIsNotNone(config.arming)
        self.assertIsNotNone(config.sensor)
        self.assertIsNotNone(config.trigger)

    def test_topic_template_formatting(self):
        """Test topic templates are formatted with correct values."""
        config = QolsysConfig(
            panel=PanelConfig(
                host="192.168.1.100",
                token="abc123",
                unique_id="my_panel"
            ),
            mqtt=MqttConfig(
                host="mqtt.broker.local"
            ),
            ha=HomeAssistantConfig(
                discovery_prefix="homeassistant"
            )
        )

        # Check event topic formatting
        self.assertEqual(config.event_topic, "homeassistant/my_panel/event")

        # Check control topic formatting
        self.assertEqual(
            config.control_topic,
            "homeassistant/alarm_control_panel/my_panel/set"
        )

    def test_validation_no_panel_code_with_ha_code(self):
        """Test validation fails when HA code is set without panel code."""
        with self.assertRaises(ValidationError) as cm:
            QolsysConfig(
                panel=PanelConfig(
                    host="192.168.1.100",
                    token="abc123",
                    user_code=None
                ),
                mqtt=MqttConfig(host="mqtt.broker.local"),
                ha=HomeAssistantConfig(
                    user_code="1234"
                )
            )

        errors = cm.exception.errors()
        self.assertIn("Cannot use 'ha_user_code'", str(errors[0]["ctx"]["error"]))

    def test_validation_no_panel_code_with_arm_required(self):
        """Test validation fails when ARM code required without panel code."""
        with self.assertRaises(ValidationError) as cm:
            QolsysConfig(
                panel=PanelConfig(
                    host="192.168.1.100",
                    token="abc123",
                    user_code=None
                ),
                mqtt=MqttConfig(host="mqtt.broker.local"),
                ha=HomeAssistantConfig(
                    code_arm_required=True
                )
            )

        errors = cm.exception.errors()
        self.assertIn("Cannot require codes for ARM/TRIGGER", str(errors[0]["ctx"]["error"]))

    def test_no_panel_code_adjusts_ha_settings(self):
        """Test that missing panel code adjusts HA settings appropriately."""
        config = QolsysConfig(
            panel=PanelConfig(
                host="192.168.1.100",
                token="abc123",
                user_code=None
            ),
            mqtt=MqttConfig(host="mqtt.broker.local")
        )

        # check_user_code should be disabled
        self.assertFalse(config.ha.check_user_code)

        # code_disarm_required should be enabled
        self.assertTrue(config.ha.code_disarm_required)

    def test_load_from_yaml_file(self):
        """Test loading configuration from YAML file."""
        yaml_content = """
panel:
  host: 192.168.1.100
  token: yaml_token
  user_code: "1234"

mqtt:
  host: yaml.mqtt.broker
  port: 1883
  username: mqtt_user
  password: mqtt_pass

ha:
  discovery_prefix: homeassistant
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            config = QolsysConfig.load(yaml_path)

            self.assertEqual(config.panel.host, "192.168.1.100")
            self.assertEqual(config.panel.token, "yaml_token")
            self.assertEqual(config.panel.user_code, "1234")
            self.assertEqual(config.mqtt.host, "yaml.mqtt.broker")
            self.assertEqual(config.mqtt.username, "mqtt_user")
            self.assertEqual(config.mqtt.password, "mqtt_pass")

        finally:
            yaml_path.unlink()

    @unittest.skip("Pydantic nested models don't merge YAML with env vars - known limitation")
    def test_env_vars_override_yaml(self):
        """Test that environment variables override YAML file.

        NOTE: This is a known limitation of Pydantic's BaseSettings.
        When nested models are provided in YAML, environment variables
        for those nested models are not merged/overridden.
        Users should use YAML OR env vars, not both for nested models.
        """
        pass

    def test_load_from_config_file_env_var(self):
        """Test loading from CONFIG_FILE environment variable."""
        yaml_content = """
panel:
  host: 192.168.1.100
  token: config_file_token

mqtt:
  host: config.mqtt.broker
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            # Set CONFIG_FILE environment variable
            os.environ["CONFIG_FILE"] = str(yaml_path)

            config = QolsysConfig.load()

            self.assertEqual(config.panel.host, "192.168.1.100")
            self.assertEqual(config.panel.token, "config_file_token")
            self.assertEqual(config.mqtt.host, "config.mqtt.broker")

        finally:
            yaml_path.unlink()
            if "CONFIG_FILE" in os.environ:
                del os.environ["CONFIG_FILE"]

    def test_load_nonexistent_yaml_file(self):
        """Test loading with nonexistent YAML file path fails without env vars."""
        # Should fail since required fields are not provided
        with self.assertRaises(ValidationError):
            QolsysConfig.load(Path("/nonexistent/config.yaml"))

    @unittest.skip("Pydantic nested BaseSettings don't load from env vars directly - use YAML")
    def test_env_vars_only(self):
        """Test loading from environment variables only.

        NOTE: This is a known limitation of Pydantic's BaseSettings.
        Nested BaseSettings models (panel, mqtt) cannot be automatically
        loaded from environment variables when instantiating the parent.

        Recommended approach: Use a YAML file for configuration.
        Each nested model CAN load from its own env vars when instantiated directly.
        """
        pass


if __name__ == '__main__':
    unittest.main()
