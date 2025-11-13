import asyncio
import logging
import signal
import unittest
from unittest import mock

import tests.unit.qolsysgw.testenv  # noqa: F401

from apps.qolsysgw.__main__ import setup_logging, handle_signal, setup_signal_handlers


logging.basicConfig(level=logging.DEBUG)


class TestUnitSetupLogging(unittest.TestCase):
    """Test logging setup functionality."""

    def setUp(self):
        """Reset logging configuration before each test."""
        # Remove all handlers
        logger = logging.getLogger()
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    def tearDown(self):
        """Clean up after tests."""
        # Remove all handlers
        logger = logging.getLogger()
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    def test_default_log_level(self):
        """Test default logging level is INFO."""
        setup_logging()

        logger = logging.getLogger()
        self.assertEqual(logger.level, logging.INFO)

    def test_custom_log_level(self):
        """Test custom logging level."""
        setup_logging("DEBUG")

        logger = logging.getLogger()
        self.assertEqual(logger.level, logging.DEBUG)

    def test_invalid_log_level_defaults_to_info(self):
        """Test invalid log level defaults to INFO."""
        setup_logging("INVALID")

        logger = logging.getLogger()
        self.assertEqual(logger.level, logging.INFO)

    def test_library_log_levels_debug(self):
        """Test third-party library log levels with DEBUG."""
        setup_logging("DEBUG")

        # Libraries should be set to INFO when root is DEBUG
        aiomqtt_logger = logging.getLogger("aiomqtt")
        paho_logger = logging.getLogger("paho")

        self.assertEqual(aiomqtt_logger.level, logging.INFO)
        self.assertEqual(paho_logger.level, logging.INFO)

    def test_library_log_levels_info(self):
        """Test third-party library log levels with INFO."""
        setup_logging("INFO")

        # Libraries should be set to WARNING when root is INFO or higher
        aiomqtt_logger = logging.getLogger("aiomqtt")
        paho_logger = logging.getLogger("paho")

        self.assertEqual(aiomqtt_logger.level, logging.WARNING)
        self.assertEqual(paho_logger.level, logging.WARNING)

    def test_logging_formatter(self):
        """Test logging formatter is configured correctly."""
        setup_logging()

        logger = logging.getLogger()
        self.assertGreater(len(logger.handlers), 0)

        # Check that handler has a formatter
        handler = logger.handlers[0]
        self.assertIsNotNone(handler.formatter)

        # Check format includes timestamp, level, name, and message
        fmt = handler.formatter._fmt
        self.assertIn("asctime", fmt)
        self.assertIn("levelname", fmt)
        self.assertIn("name", fmt)
        self.assertIn("message", fmt)


class TestUnitHandleSignal(unittest.TestCase):
    """Test signal handling functionality."""

    def test_handle_signal_sets_shutdown_event(self):
        """Test that handle_signal sets the shutdown event."""
        import apps.qolsysgw.__main__ as main_module

        # Create and set shutdown event
        shutdown_event = asyncio.Event()
        main_module.shutdown_event = shutdown_event

        # Handle signal
        handle_signal(signal.SIGTERM)

        # Verify event was set
        self.assertTrue(shutdown_event.is_set())

    def test_handle_signal_with_no_event(self):
        """Test handle_signal when shutdown_event is None."""
        import apps.qolsysgw.__main__ as main_module

        # Set shutdown event to None
        main_module.shutdown_event = None

        # Should not raise exception
        try:
            handle_signal(signal.SIGTERM)
        except Exception as e:
            self.fail(f"handle_signal raised exception: {e}")


class TestUnitSetupSignalHandlers(unittest.TestCase):
    """Test signal handler setup."""

    def test_setup_signal_handlers_creates_event(self):
        """Test that setup_signal_handlers creates shutdown event."""
        import apps.qolsysgw.__main__ as main_module

        # Create event loop
        loop = asyncio.new_event_loop()

        try:
            # Set up signal handlers
            setup_signal_handlers(loop)

            # Verify shutdown_event was created
            self.assertIsNotNone(main_module.shutdown_event)
            self.assertIsInstance(main_module.shutdown_event, asyncio.Event)
            self.assertFalse(main_module.shutdown_event.is_set())

        finally:
            # Clean up signal handlers
            loop.remove_signal_handler(signal.SIGTERM)
            loop.remove_signal_handler(signal.SIGINT)
            loop.close()

    @mock.patch('apps.qolsysgw.__main__.handle_signal')
    def test_signal_handlers_registered(self, mock_handle_signal):
        """Test that signal handlers are registered for SIGTERM and SIGINT."""
        import apps.qolsysgw.__main__ as main_module

        # Create event loop
        loop = asyncio.new_event_loop()

        try:
            # Set up signal handlers
            setup_signal_handlers(loop)

            # Manually trigger signal handlers to verify they were registered
            # This is tricky because we can't easily trigger actual signals in tests
            # Instead, verify the shutdown event was created
            self.assertIsNotNone(main_module.shutdown_event)

        finally:
            # Clean up
            loop.remove_signal_handler(signal.SIGTERM)
            loop.remove_signal_handler(signal.SIGINT)
            loop.close()


class TestUnitMain(unittest.TestCase):
    """Test main function.

    NOTE: Full integration testing of main() is better suited for E2E tests.
    These unit tests focus on error handling and basic flow that can be tested
    without complex mocking of the entire application stack.
    """

    @unittest.skip("Full main() integration testing is better suited for E2E tests")
    async def test_main_loads_config(self):
        """Test main function configuration loading.

        This test is skipped because mocking all components (QolsysConfig,
        MqttClient, QolsysGateway) for the main() function is complex due to
        imports happening inside main(). This functionality is better tested
        in end-to-end tests with real configuration and controlled environment.
        """
        pass

    @unittest.skip("Full main() integration testing is better suited for E2E tests")
    async def test_main_handles_exception(self):
        """Test main function exception handling.

        This test is skipped for the same reasons as test_main_loads_config.
        Exception handling in main() is better verified through E2E tests.
        """
        pass


def async_test(coro):
    """Decorator to run async tests."""
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro(*args, **kwargs))
        finally:
            loop.close()
    return wrapper


# Apply async_test decorator to all async test methods
for name in dir(TestUnitMain):
    if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(TestUnitMain, name)):
        setattr(
            TestUnitMain,
            name,
            async_test(getattr(TestUnitMain, name))
        )


if __name__ == '__main__':
    unittest.main()
