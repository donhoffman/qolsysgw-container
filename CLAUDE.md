# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Qolsys Gateway (`qolsysgw`) is an AppDaemon automation that acts as a bridge between Qolsys IQ Panel alarm systems (2/2+/4) and Home Assistant via MQTT. It connects to the panel using the Control4 protocol and publishes sensor/partition states to Home Assistant using MQTT discovery.

This is a Python 3.8+ project that runs as an AppDaemon app, distributed via HACS (Home Assistant Community Store) and PyPI.

## Build and Test Commands

### Running Tests

```bash
# Run all tests (lint + unit + integration)
omni test

# Run linting only
omni test lint
# Or directly:
flake8 apps/ tests/

# Run unit and integration tests
omni test unit
# Or directly:
pytest --cache-clear tests/unit/ tests/integration/

# Run end-to-end tests (requires Docker)
omni test e2e
# Or directly:
pytest --cache-clear tests/end-to-end/
```

### Building

```bash
# Build the package (creates dist/ with wheel and source distribution)
omni build
# Or directly:
hatch build

# Publish to PyPI (requires clean git tag)
omni publish
# Or directly:
hatch publish
```

### Test Requirements

The project uses different test requirement files:
- `tests/requirements.txt` - Core test dependencies
- `tests/requirements-tools.txt` - Testing tools (installed by omni)
- `tests/end-to-end/requirements.txt` - E2E test dependencies

Python version is automatically matched to AppDaemon's latest Docker image in CI.

## Code Architecture

### High-Level Structure

The codebase has three main subsystems:

1. **Qolsys Panel Interface (`apps/qolsysgw/qolsys/`)** - Manages communication with the Qolsys alarm panel
2. **MQTT Interface (`apps/qolsysgw/mqtt/`)** - Handles MQTT messaging and Home Assistant MQTT discovery
3. **Gateway Orchestration (`apps/qolsysgw/gateway.py`)** - Main AppDaemon app that ties everything together

### Main Components

#### Gateway (`gateway.py`)
- `QolsysGateway` class extends AppDaemon's `Mqtt` class
- Initializes three async workflows:
  1. Panel communication via `QolsysSocket`
  2. MQTT event listener (`MqttQolsysEventListener`)
  3. MQTT control listener (`MqttQolsysControlListener`)
- Manages the observable state pattern through `QolsysState`
- Creates `MqttUpdater` to automatically publish state changes to MQTT

#### Qolsys Panel Interface (`qolsys/`)
- **`socket.py`**: `QolsysSocket` - Async SSL connection to panel, sends keep-alive every 4 minutes
- **`actions.py`**: Outbound commands to panel (INFO, ARMING, DISARM, TRIGGER)
- **`events.py`**: Inbound events from panel (parsed using class hierarchy with `find_subclass`)
- **`control.py`**: Control messages from Home Assistant (ARM_STAY, ARM_AWAY, DISARM, TRIGGER)
- **`state.py`**: `QolsysState` - Central state manager using observable pattern
- **`partition.py`**: `QolsysPartition` - Represents alarm partitions (contains sensors)
- **`sensors.py`**: Type-specific sensor classes (DoorWindow, Motion, Smoke, etc.)
- **`config.py`**: Configuration object built from `apps.yaml` parameters
- **`observable.py`**: Observer pattern implementation for state changes

#### MQTT Interface (`mqtt/`)
- **`updater.py`**:
  - `MqttUpdater` - Observes state changes and publishes to MQTT
  - `MqttWrapper` hierarchy - Wraps partitions/sensors to send MQTT discovery configs
- **`listener.py`**:
  - `MqttQolsysEventListener` - Subscribes to panel events (from panel → MQTT → updater)
  - `MqttQolsysControlListener` - Subscribes to HA control commands
- **`utils.py`**: Helper functions for MQTT topics/names

### Key Patterns

#### Observable Pattern
State changes flow through an observer pattern:
1. Panel sends event → `QolsysSocket` parses → Updates `QolsysState`
2. `QolsysState` notifies observers (partitions, sensors)
3. `MqttUpdater` receives notifications → Publishes to MQTT
4. Home Assistant receives MQTT messages

#### Event/Action Parsing
Uses a dynamic class discovery pattern (`find_subclass` in `utils.py`):
- Base classes: `QolsysEvent`, `QolsysAction`, `QolsysControl`
- Subclasses define `__event_type__`, `__info_type__`, or `__action_type__` class attributes
- `from_json()` methods automatically route to correct subclass

#### Async Workflows
Three concurrent async tasks:
1. **Panel listener** (`QolsysSocket.listen()`) - Maintains connection, parses events
2. **Keep-alive sender** (`QolsysSocket.keep_alive()`) - Sends heartbeat every 4 minutes
3. **MQTT listeners** - React to incoming MQTT messages via AppDaemon event system

### Test Structure

- `tests/unit/` - Unit tests with mocked AppDaemon/MQTT
- `tests/integration/` - Integration tests with mock panel
- `tests/end-to-end/` - Full stack tests with Docker (AppDaemon + MQTT + mock panel)
- `tests/mock_modules/` - Mock implementations of AppDaemon and test utilities

### Important Configuration

The gateway is configured via AppDaemon's `apps.yaml`:
- Required: `panel_host`, `panel_token` (from Qolsys Control4 interface)
- Optional: User codes, arm delays, bypass settings, MQTT topics
- See README.md configuration section for full details

### Logging

The gateway redirects Python's `logging` module to AppDaemon's logger:
- Uses custom `AppDaemonLoggingHandler` and `AppDaemonLoggingFilter`
- All submodules use standard `logging.getLogger(__name__)`
- AppDaemon log level controls what appears in logs

## Development Notes

- The codebase supports multiple Qolsys panels via `panel_unique_id` configuration
- MQTT discovery messages use Home Assistant's autodiscovery protocol
- Panel connection uses SSL but doesn't verify certificates (self-signed)
- Session tokens prevent unauthorized MQTT control messages
- The project uses `hatch` for building/publishing, `pytest` for testing, `flake8` for linting

## Workflow for Tracking Progress

When working on tasks tracked in **PLAN.md** with checkboxes:

### Updating Checkmarks
- **IMPORTANT**: After completing each task/checkbox, proactively ask the user for permission to update the checkmark in PLAN.md
- Do NOT wait for the user to prompt you to update the checkmarks
- Do NOT update checkmarks without explicit user permission
- Example: "I've completed creating `requirements.txt`. May I update the checkbox in PLAN.md?"

### Why This Matters
- Keeps the user informed of progress in real-time
- Ensures the user has visibility and control over the project status
- Prevents checkmarks from getting out of sync with actual work completed
- Allows the user to verify work before marking it complete

### Implementation Note
This workflow applies to any checklist-based planning document, not just PLAN.md. Always check with the user before updating progress indicators.