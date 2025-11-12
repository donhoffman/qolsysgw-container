"""Qolsys Gateway exception classes."""

from datetime import datetime, timezone


class QolsysException(Exception):
    """Base exception class for Qolsys Gateway errors.

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


class QolsysGwConfigIncomplete(QolsysException):
    """Raised when required configuration parameters are missing."""

    pass


class QolsysGwConfigError(QolsysException):
    """Raised when configuration parameters are invalid."""

    pass


class UnableToParseEventException(QolsysException):
    """Raised when a panel event cannot be parsed."""

    pass


class UnableToParseSensorException(QolsysException):
    """Raised when a sensor configuration cannot be parsed."""

    pass


class UnknownQolsysControlException(QolsysException):
    """Raised when an unknown control command is received."""

    pass


class UnknownQolsysEventException(QolsysException):
    """Raised when an unknown event type is received from the panel."""

    pass


class UnknownQolsysSensorException(QolsysException):
    """Raised when an unknown sensor type is encountered."""

    pass


class MissingUserCodeException(QolsysException):
    """Raised when a user code is required but not provided."""

    pass


class InvalidUserCodeException(QolsysException):
    """Raised when provided user code is invalid."""

    pass


class QolsysSyncException(QolsysException):
    """Raised when state synchronization with the panel is lost.

    This occurs when the gateway's internal state no longer matches
    the panel's actual state (e.g., zone or partition not found).
    """

    pass


class QolsysConnectionException(QolsysException):
    """Raised when there is a connection issue with the Qolsys panel.

    This includes socket/writer not available or other connection problems.
    """

    pass
