"""MQTT-related exception classes."""

from datetime import datetime, timezone


class MqttException(Exception):
    """Base exception class for MQTT-related errors.

    Automatically records the timestamp when the exception occurred
    and can optionally register with a global STATE object.
    """

    STATE = None

    def __init__(self, *args, **_kwargs):
        """Initialize exception with timestamp.

        Args:
            *args: Positional arguments passed to Exception
            **_kwargs: Keyword arguments (unused, accepted for compatibility)
        """
        super().__init__(*args)

        self._at = datetime.now(timezone.utc).isoformat()

        if self.STATE:
            self.STATE.last_exception = self

    @property
    def at(self) -> str:
        """Return ISO format timestamp of when exception occurred.

        Returns:
            ISO format timestamp string
        """
        return self._at


class UnknownMqttWrapperException(MqttException):
    """Raised when unable to find appropriate MQTT wrapper for an object."""

    pass


class UnknownDeviceClassException(MqttException):
    """Raised when unable to determine Home Assistant device class for a sensor."""

    pass


class MqttPluginUnavailableException(MqttException):
    """Raised when MQTT plugin is not available."""

    pass
