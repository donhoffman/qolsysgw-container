"""Main entry point for Qolsys Gateway standalone application."""

import asyncio
import logging
import signal
import sys
from functools import partial
from pathlib import Path
from typing import Optional

from apps.qolsysgw.config import QolsysConfig

LOGGER = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_event: Optional[asyncio.Event] = None


def setup_logging(log_level: str = "INFO") -> None:
    """Configure logging with plain text format and timestamps.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Parse log level
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO

    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
    )

    # Set third-party library log levels to reduce noise
    # If DEBUG: set libraries to INFO (see some activity but not every message)
    # If INFO or higher: set libraries to WARNING (only warnings/errors)
    if numeric_level == logging.DEBUG:
        library_level = logging.INFO
    else:
        library_level = logging.WARNING

    logging.getLogger("aiomqtt").setLevel(library_level)
    logging.getLogger("paho").setLevel(library_level)

    LOGGER.info(f"Logging configured at {log_level} level")
    if library_level != numeric_level:
        LOGGER.debug(
            f"Third-party libraries (aiomqtt, paho) set to "
            f"{logging.getLevelName(library_level)} level"
        )


def handle_signal(sig: int) -> None:
    """Handle shutdown signals.

    Args:
        sig: Signal number
    """
    signal_name = signal.Signals(sig).name
    LOGGER.info(f"Received {signal_name}, initiating graceful shutdown...")

    if shutdown_event:
        shutdown_event.set()


def setup_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    """Set up signal handlers for graceful shutdown.

    Args:
        loop: Event loop to use for signal handling
    """
    global shutdown_event
    shutdown_event = asyncio.Event()

    # Handle SIGTERM and SIGINT
    for sig in (signal.SIGTERM, signal.SIGINT):
        # noinspection PyTypeChecker
        loop.add_signal_handler(sig, partial(handle_signal, sig))

    LOGGER.info("Signal handlers registered (SIGTERM, SIGINT)")


async def main() -> int:
    """Main async entry point.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        # Load configuration
        config_file = Path(".env") if Path(".env").exists() else None
        config = QolsysConfig.load(config_file)

        LOGGER.info("Configuration loaded successfully")
        LOGGER.info(f"Panel: {config.panel.host}")
        LOGGER.info(f"MQTT: {config.mqtt.host}:{config.mqtt.port}")
        LOGGER.info(f"HA Discovery: {config.ha.discovery_prefix}")

        # Import gateway here to avoid circular imports
        from apps.qolsysgw.mqtt.client import MqttClient
        from apps.qolsysgw.gateway import QolsysGateway

        # Create MQTT client
        mqtt_client = MqttClient(
            host=config.mqtt.host,
            port=config.mqtt.port,
            username=config.mqtt.username,
            password=config.mqtt.password,
            will_topic=config.mqtt.will_topic,
            will_payload=config.mqtt.will_payload,
            birth_topic=config.mqtt.birth_topic,
            birth_payload=config.mqtt.birth_payload,
            qos=config.mqtt.qos,
            retain=config.mqtt.retain,
        )

        # Create gateway instance
        gateway = QolsysGateway(config=config, mqtt_client=mqtt_client)

        LOGGER.info("Starting Qolsys Gateway...")

        # Run main application with TaskGroup for automatic cleanup
        async with asyncio.TaskGroup() as tg:
            # Start MQTT client with auto-reconnect
            mqtt_task = tg.create_task(
                mqtt_client.run_with_reconnect(),
                name="mqtt_client",
            )

            # Start gateway tasks
            gateway_task = tg.create_task(
                gateway.run(),
                name="gateway",
            )

            # Wait for shutdown signal
            shutdown_task = tg.create_task(
                shutdown_event.wait(),
                name="shutdown_waiter",
            )

            LOGGER.info("All tasks started, waiting for shutdown signal...")

            # This will block until shutdown_event is set or a task fails
            await shutdown_task

            LOGGER.info("Shutdown signal received, stopping tasks...")

            # Cancel all other tasks
            mqtt_task.cancel()
            gateway_task.cancel()

        LOGGER.info("All tasks stopped gracefully")
        return 0

    except KeyboardInterrupt:
        LOGGER.info("Interrupted by user (Ctrl+C)")
        return 0

    except Exception as e:
        LOGGER.error(f"Fatal error: {e}", exc_info=True)
        return 1


def run() -> None:
    """Run the application."""
    # Parse log level from environment or use INFO
    import os
    log_level = os.getenv("LOG_LEVEL", "INFO")

    # Set up logging first
    setup_logging(log_level)

    LOGGER.info("=" * 60)
    LOGGER.info("Qolsys Gateway v2.0.0-dev")
    LOGGER.info("=" * 60)

    loop = None
    try:
        # Create event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Set up signal handlers
        setup_signal_handlers(loop)

        # Run main application
        exit_code = loop.run_until_complete(main())

        LOGGER.info("Application shutdown complete")
        sys.exit(exit_code)

    except Exception as e:
        LOGGER.critical(f"Failed to start application: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # Clean up event loop
        # noinspection PyBroadException
        try:
            if loop is not None:
                loop.close()
        except Exception:
            pass


if __name__ == "__main__":
    run()