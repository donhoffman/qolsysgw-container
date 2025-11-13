"""Configuration management for Qolsys Gateway using Pydantic."""

import logging
import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOGGER = logging.getLogger(__name__)


class PanelConfig(BaseSettings):
    """Qolsys Panel configuration."""

    model_config = SettingsConfigDict(
        env_prefix="QOLSYS_PANEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(..., description="Panel hostname or IP address")
    port: Optional[int] = Field(default=None, description="Panel port (default: auto)")
    mac: Optional[str] = Field(default=None, description="Panel MAC address (auto-detected if not set)")
    token: str = Field(..., description="Panel secure token from Control4 interface")
    user_code: Optional[str] = Field(
        default=None,
        description="User code for arming/disarming (4 or 6 digits)",
    )
    unique_id: str = Field(
        default="qolsys_panel",
        description="Unique identifier for this panel (used in MQTT topics)",
    )
    device_name: str = Field(
        default="Qolsys Panel",
        description="Device name for Home Assistant",
    )

    @field_validator("user_code")
    @classmethod
    def validate_user_code(cls, v: Optional[str]) -> Optional[str]:
        """Validate user code is 4 or 6 digits."""
        if v is None:
            return v

        # Convert to string and remove any whitespace
        code = str(v).strip()

        # Check if it's all digits
        if not code.isdigit():
            raise ValueError("User code must contain only digits")

        # Check length (4 or 6 digits)
        if len(code) not in (4, 6):
            raise ValueError("User code must be either 4 or 6 digits")

        return code


class ArmingConfig(BaseSettings):
    """Arming configuration."""

    model_config = SettingsConfigDict(
        env_prefix="QOLSYS_ARM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    away_exit_delay: Optional[int] = Field(
        default=None,
        description="Exit delay for arm away (seconds)",
    )
    stay_exit_delay: Optional[int] = Field(
        default=None,
        description="Exit delay for arm stay (seconds)",
    )
    away_bypass: Optional[bool] = Field(
        default=None,
        description="Allow bypass when arming away",
    )
    stay_bypass: Optional[bool] = Field(
        default=None,
        description="Allow bypass when arming stay",
    )
    type_custom_bypass: str = Field(
        default="arm_away",
        description="Arm type for custom bypass (arm_away or arm_stay)",
    )

    @field_validator("type_custom_bypass")
    @classmethod
    def validate_arm_type(cls, v: str) -> str:
        """Validate arm type is arm_away or arm_stay."""
        arm_type = v.lower().strip()
        if arm_type not in ("arm_away", "arm_stay"):
            raise ValueError("arm_type_custom_bypass must be 'arm_away' or 'arm_stay'")
        return arm_type


class MqttConfig(BaseSettings):
    """MQTT broker configuration."""

    model_config = SettingsConfigDict(
        env_prefix="MQTT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(..., description="MQTT broker hostname or IP")
    port: int = Field(default=1883, description="MQTT broker port")
    username: Optional[str] = Field(default=None, description="MQTT username")
    password: Optional[str] = Field(default=None, description="MQTT password")

    birth_topic: str = Field(
        default="homeassistant/status",
        description="Topic for birth message",
    )
    birth_payload: str = Field(
        default="online",
        description="Payload for birth message",
    )
    will_topic: str = Field(
        default="homeassistant/status",
        description="Topic for last will message",
    )
    will_payload: str = Field(
        default="offline",
        description="Payload for last will message",
    )
    qos: int = Field(
        default=1,
        ge=0,
        le=2,
        description="MQTT QoS level (0-2)",
    )
    retain: bool = Field(
        default=True,
        description="Retain MQTT messages",
    )


class HomeAssistantConfig(BaseSettings):
    """Home Assistant integration configuration."""

    model_config = SettingsConfigDict(
        env_prefix="HA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discovery_prefix: str = Field(
        default="homeassistant",
        description="MQTT discovery prefix",
    )
    check_user_code: bool = Field(
        default=True,
        description="Check user code in Home Assistant",
    )
    user_code: Optional[str] = Field(
        default=None,
        description="User code for Home Assistant (if different from panel code)",
    )
    code_arm_required: bool = Field(
        default=False,
        description="Require code for arming",
    )
    code_disarm_required: bool = Field(
        default=False,
        description="Require code for disarming",
    )
    code_trigger_required: bool = Field(
        default=False,
        description="Require code for triggering",
    )

    @field_validator("user_code")
    @classmethod
    def validate_user_code(cls, v: Optional[str]) -> Optional[str]:
        """Validate user code is 4 or 6 digits."""
        if v is None:
            return v

        code = str(v).strip()
        if not code.isdigit():
            raise ValueError("HA user code must contain only digits")
        if len(code) not in (4, 6):
            raise ValueError("HA user code must be either 4 or 6 digits")

        return code


class SensorConfig(BaseSettings):
    """Sensor configuration."""

    model_config = SettingsConfigDict(
        env_prefix="QOLSYS_SENSOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    default_device_class: str = Field(
        default="safety",
        description="Default device class for sensors",
    )
    enable_static_by_default: bool = Field(
        default=False,
        description="Enable static sensors by default",
    )


class TriggerConfig(BaseSettings):
    """Trigger configuration."""

    model_config = SettingsConfigDict(
        env_prefix="QOLSYS_TRIGGER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    default_command: Optional[str] = Field(
        default=None,
        description="Default trigger command",
    )

    @field_validator("default_command")
    @classmethod
    def validate_trigger_command(cls, v: Optional[str]) -> Optional[str]:
        """Validate trigger command."""
        if v is None:
            return v

        cmd = v.upper().strip()
        valid = {"TRIGGER", "TRIGGER_AUXILIARY", "TRIGGER_FIRE", "TRIGGER_POLICE"}

        if cmd not in valid:
            raise ValueError(
                f"Invalid trigger command '{cmd}'; must be one of {', '.join(valid)}"
            )

        return cmd


class QolsysConfig(BaseSettings):
    """Main configuration for Qolsys Gateway."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Sub-configurations
    panel: PanelConfig
    arming: ArmingConfig = Field(default_factory=ArmingConfig)
    mqtt: MqttConfig
    ha: HomeAssistantConfig = Field(default_factory=HomeAssistantConfig)
    sensor: SensorConfig = Field(default_factory=SensorConfig)
    trigger: TriggerConfig = Field(default_factory=TriggerConfig)

    # Optional YAML config file
    config_file: Optional[Path] = Field(
        default=None,
        description="Path to optional YAML configuration file",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )

    # Additional fields for backward compatibility
    event_topic: str = Field(
        default="qolsys/{panel_unique_id}/event",
        description="Topic for panel events",
    )
    control_topic: str = Field(
        default="{discovery_prefix}/alarm_control_panel/{panel_unique_id}/set",
        description="Topic for control commands",
    )
    user_control_token: Optional[str] = Field(
        default=None,
        description="User control token for MQTT authentication",
    )

    @model_validator(mode="after")
    def validate_and_apply_defaults(self) -> "QolsysConfig":
        """Validate configuration and apply smart defaults."""
        # Format topic templates
        self.event_topic = self.event_topic.format(
            panel_unique_id=self.panel.unique_id
        )
        self.control_topic = self.control_topic.format(
            discovery_prefix=self.ha.discovery_prefix,
            panel_unique_id=self.panel.unique_id,
        )

        # Validate HA user code settings
        if self.panel.user_code is None:
            if self.ha.user_code:
                raise ValueError(
                    "Cannot use 'ha_user_code' if 'panel_user_code' is not set"
                )

            if self.ha.code_arm_required or self.ha.code_trigger_required:
                raise ValueError(
                    "Cannot require codes for ARM/TRIGGER without panel_user_code"
                )

            # Without panel code, HA cannot check codes
            self.ha.check_user_code = False

            # Without panel code, we need HA to provide one for disarm
            self.ha.code_disarm_required = True

            LOGGER.warning(
                "No panel_user_code configured - disarm will require code from HA"
            )

        return self

    @classmethod
    def load(cls, config_file: Optional[Path] = None) -> "QolsysConfig":
        """Load configuration from environment and optional YAML file.

        Args:
            config_file: Optional path to YAML configuration file

        Returns:
            Loaded configuration

        Note:
            Environment variables take precedence over YAML file values.
        """
        yaml_data = {}

        # Load YAML file if provided
        if config_file and config_file.exists():
            LOGGER.info(f"Loading configuration from {config_file}")
            with open(config_file) as f:
                yaml_data = yaml.safe_load(f) or {}

        # Check for CONFIG_FILE environment variable
        env_config_file = os.getenv("CONFIG_FILE")
        if env_config_file and not config_file:
            config_path = Path(env_config_file)
            if config_path.exists():
                LOGGER.info(f"Loading configuration from {config_path}")
                with open(config_path) as f:
                    yaml_data = yaml.safe_load(f) or {}

        # Merge YAML data with environment variables
        # Environment variables will override YAML values automatically via Pydantic
        if yaml_data:
            return cls(**yaml_data)
        else:
            # When loading from env vars only, we need to explicitly construct nested models
            # since Pydantic doesn't automatically instantiate nested BaseSettings from env
            return cls(
                panel=PanelConfig(),
                mqtt=MqttConfig(),
                arming=ArmingConfig(),
                ha=HomeAssistantConfig(),
                sensor=SensorConfig(),
                trigger=TriggerConfig(),
            )
