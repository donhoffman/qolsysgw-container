# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## General Instructions

These instructions apply to all tasks you perform in this repository. and should be followed carefully.
- Remain critical and skeptical about my thinking at all times. Maintain consistent intellectual standards throughout our conversation. Don’t lower your bar for evidence or reasoning quality just because we’ve been talking longer or because I seem frustrated.
- For Python projects, always follow PEP 8 style guidelines unless explicitly instructed otherwise.
- For Python projects, always use type hints for all functions and methods unless explicitly instructed otherwise.
- For Python projects, always use Google-style docstrings for all functions and methods unless explicitly instructed otherwise.
- For Python projects, prefer 3.13 wherever possible, but ensure compatibility with the specified minimum Python version in PROJECT_SPEC.md. Lower versions are allowed if dependencies require it.
- For Python projects, always use `black` for code formatting unless explicitly instructed otherwise.
- For Python projects, prefer absolute imports over relative imports unless explicitly instructed otherwise.
- Assume all development is done in a virtual environment unless explicitly instructed otherwise.
- Assume all development is done on macOS 26 using PyCharm (>2025.2.4) unless explicitly instructed otherwise.
- Use PyCharm MCP (Model Context Protocol) features to assist with code generation, refactoring, and navigation.
- 

## Project Overview

Qolsys Gateway (`qolsysgw`) is a standalone Python application that acts as a bridge between Qolsys IQ Panel alarm systems (2/2+/4) and Home Assistant via MQTT. It connects to the panel using the Control4 protocol and publishes sensor/partition states to Home Assistant using MQTT discovery.

This is a Python 3.13+ project that runs as a standalone Docker container, distributed via GitHub Container Registry (GHCR) and PyPI.

**Note**: Version 1.x was an AppDaemon automation. Version 2.0+ runs standalone without AppDaemon.

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

### Docker Commands

```bash
# Build Docker image
docker build -t qolsysgw:latest .

# Run with docker-compose (requires .env file)
docker compose up -d

# View logs
docker compose logs -f

# Stop container
docker compose down

# Restart container
docker compose restart

# Check container status and health
docker compose ps

# Execute health check manually
docker compose exec qolsysgw /app/docker-healthcheck.sh
```

**Note**: The Docker container preserves the `apps/` directory structure to maintain absolute imports used in development.

### Test Requirements

**⚠️ TESTS TEMPORARILY DISABLED (v2.0.0)**

The test suite has been temporarily disabled in GitHub Actions due to the v2.0.0 architectural rewrite from AppDaemon to standalone. The existing tests were built around AppDaemon patterns and require a complete rewrite.

**Current Status**:
- GitHub Actions test jobs are commented out (`.github/workflows/build.yaml`)
- Linting still runs and passes via GitHub Actions
- Core functionality validated through manual testing against real hardware
- Some unit tests (e.g., `test_client.py`, `test_config.py`) were updated and can serve as reference

**Future Work**:
- Tests will be rebuilt from scratch for the standalone architecture
- Focus on integration tests with real MQTT broker (testcontainers)
- Remove all AppDaemon-specific test infrastructure
- Build tests incrementally as features stabilize

The project uses different test requirement files (for future use):
- `tests/requirements.txt` - Core test dependencies
- `tests/requirements-tools.txt` - Testing tools (installed by omni)
- `tests/end-to-end/requirements.txt` - E2E test dependencies

## Code Architecture

### High-Level Structure

The codebase has three main subsystems:

1. **Qolsys Panel Interface (`apps/qolsysgw/qolsys/`)** - Manages communication with the Qolsys alarm panel
2. **MQTT Interface (`apps/qolsysgw/mqtt/`)** - Handles MQTT messaging and Home Assistant MQTT discovery
3. **Gateway Orchestration (`apps/qolsysgw/gateway.py`)** - Main application that orchestrates the gateway

### Main Components

#### Gateway (`gateway.py`)
- `QolsysGateway` class - standalone gateway orchestrator
- Initializes four async workflows:
  1. Panel communication via `QolsysSocket`
  2. MQTT event listener (`MqttQolsysEventListener`)
  3. MQTT control listener (`MqttQolsysControlListener`)
  4. HA status listener (`MqttHAStatusListener`) - detects HA restarts
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
- **`config.py`**: Configuration object built from environment variables and optional YAML config
- **`observable.py`**: Observer pattern implementation for state changes

#### MQTT Interface (`mqtt/`)
- **`client.py`**: `MqttClient` - aiomqtt wrapper with auto-reconnect and LWT support
- **`updater.py`**:
  - `MqttUpdater` - Observes state changes and publishes to MQTT
  - `MqttWrapper` hierarchy - Wraps partitions/sensors to send MQTT discovery configs
- **`listener.py`**:
  - `MqttQolsysEventListener` - Subscribes to panel events (from panel → MQTT → updater)
  - `MqttQolsysControlListener` - Subscribes to HA control commands
  - `MqttHAStatusListener` - Detects HA restarts and triggers entity reconfiguration
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
Two concurrent async tasks:
1. **Panel listener** (`QolsysSocket.listen()`) - Maintains connection, parses events
2. **Keep-alive sender** (`QolsysSocket.keep_alive()`) - Sends heartbeat every 4 minutes
3. **MQTT listeners** - React to incoming MQTT messages via direct subscriptions

#### HA Restart Detection
When Home Assistant restarts, it publishes "online" to `homeassistant/status`. The `MqttHAStatusListener` detects this and triggers reconfiguration of all entities, ensuring HA has the latest discovery configs and current state.

### Test Structure

**⚠️ Tests currently disabled - see "Test Requirements" section above**

When rebuilt, the test structure will be:
- `tests/unit/` - Unit tests with mocked MQTT client
- `tests/integration/` - Integration tests with real MQTT broker (testcontainers)
- `tests/end-to-end/` - Full stack tests with Docker (standalone container + MQTT + mock panel)
- `tests/mock_modules/` - Mock implementations and test utilities

**Current state**: Existing tests are based on AppDaemon patterns and are not compatible with the v2.0.0 standalone architecture. They will be rewritten from scratch in future work.

### Important Configuration

The gateway is configured via environment variables and optional YAML config:
- Required: `QOLSYS_PANEL_HOST`, `QOLSYS_PANEL_TOKEN` (from Qolsys Control4 interface)
- Required: `MQTT_HOST` (MQTT broker hostname)
- Optional: User codes, arm delays, bypass settings, MQTT topics, HA status detection
- See `.env.example` for all configuration options

### Logging

The gateway uses standard Python logging:
- Logs to stdout with plain text format and timestamps
- All submodules use standard `logging.getLogger(__name__)`
- Log level controlled via `LOG_LEVEL` environment variable (DEBUG, INFO, WARNING, ERROR, CRITICAL)

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

## Git Commit Workflow

### Creating Commits
- **IMPORTANT**: Do NOT create git commits until explicitly instructed by the user
- The user may want to batch multiple changes together before committing
- After making changes, inform the user what files were modified and wait for commit instruction
- Example: "I've updated `.gitignore` with Python, macOS, and PyCharm ignore patterns. Let me know when you'd like me to commit these changes."
- When the user instructs you to commit, create a descriptive commit message summarizing the changes made