# Plan: Remove AppDaemon Dependency and Run as Standalone Docker Container

## Executive Summary

This document outlines the changes needed to convert qolsysgw from an AppDaemon automation to a standalone Python application running in a Docker container, communicating directly with MQTT and Home Assistant.

## Design Decisions

The following key decisions have been made for the implementation:

### ✅ Configuration Method
**Decision**: Environment variables for all configuration, with secrets via env vars and optional YAML config file support (env vars take precedence).

**Rationale**: Docker-friendly, follows 12-factor app methodology, easy to manage in container orchestration platforms.

### ✅ Multi-Panel Support
**Decision**: Single panel per container.

**Rationale**: Simpler architecture, cloud-native approach, better for orchestration and scaling. Users with multiple panels run multiple containers.

### ✅ MQTT Library
**Decision**: `aiomqtt` (>=2.0.0)

**Rationale**: Modern async-first library, perfect for Python 3.13, built on reliable paho-mqtt, excellent async/await patterns.

### ✅ Docker Base Image
**Decision**: `python:3.13-slim`

**Rationale**: Balance of image size and compatibility, minimal Debian-based image with good security posture.

### ✅ Health Checks
**Decision**: Basic health check (MQTT connected AND Panel connected).

**Rationale**: Start simple with essential connectivity checks. Advanced metrics (Prometheus, etc.) can be added later if needed.

### ✅ Graceful Shutdown
**Decision**: Full implementation
- SIGTERM/SIGINT handling for clean shutdown
- Auto-reconnect for both MQTT and Panel
- State persistence deferred to future release

**Rationale**: Required for production reliability. State persistence is nice-to-have and can be added incrementally.

### ✅ Version Strategy
**Decision**: Clean break at v2.0.0 with comprehensive migration guide.

**Rationale**: Cleaner codebase, easier maintenance. AppDaemon version (v1.x) can be maintained in separate branch during transition period if needed.

### ✅ Deployment & Distribution
**Decisions**:
- **Deployment Examples**: Docker Compose with advanced features (networks/volumes)
- **Container Registry**: GitHub Container Registry (ghcr.io)
- **CI/CD**: Automatic builds on tagged releases only
- **Logging Format**: Plain text with timestamps (human-readable)
- **Migration**: Clean break, no migration guide (users adapt or stay on v1.x)

**Rationale**: Advanced Docker Compose covers most use cases, GHCR integrates well with GitHub Actions, tagged releases ensure stable builds, plain text logging is easier to debug during development, clean break simplifies codebase.

## Current AppDaemon Dependencies

### What AppDaemon Provides

1. **MQTT Integration**
   - `mqtt_publish(topic, payload, namespace)` - Publish messages
   - `mqtt_subscribe(topic, namespace)` - Subscribe to topics
   - `listen_event()` - Listen for MQTT messages
   - Plugin configuration (birth/will topics, credentials)

2. **Task Management**
   - `create_task()` - Create asyncio tasks
   - Automatic task cleanup on shutdown

3. **Configuration**
   - Loads from `apps.yaml`
   - Provides `self.args` dict to app

4. **Logging**
   - `self.log()` - AppDaemon's logging system
   - Currently redirected to Python's `logging` module

5. **Lifecycle Hooks**
   - `initialize()` - Startup
   - `terminate()` - Shutdown

### Files Currently Using AppDaemon

- `apps/qolsysgw/gateway.py` - Extends `Mqtt` class, uses all features above
- `apps/qolsysgw/mqtt/listener.py` - Uses `app.mqtt_subscribe()` and `app.listen_event()`
- Tests mock AppDaemon components

## Required Changes

### 1. Create Standalone Application Entry Point

**New file**: `qolsysgw/__main__.py` or `qolsysgw/main.py`

**Responsibilities**:
- Load configuration from environment/files
- Initialize logging (structured logging for containers)
- Create and run the main application
- Handle SIGTERM/SIGINT for graceful shutdown
- Run asyncio event loop

**Python 3.13 features to use**:
- Modern type hints with `type` statement (PEP 695)
- Improved error messages
- `asyncio.TaskGroup` for better task management (available in 3.11+, refined in 3.13)

### 2. Replace AppDaemon MQTT with Direct MQTT Client

**Changes to `gateway.py`**:
- Remove `Mqtt` base class inheritance
- Remove AppDaemon logging handlers
- Create standalone `QolsysGateway` class
- Add `MqttClient` wrapper using `aiomqtt`

**New component**: `mqtt/client.py`
```python
class MqttClient:
    - async connect()
    - async disconnect()
    - async publish(topic, payload, retain=False)
    - async subscribe(topic, callback)
    - Connection management with auto-reconnect
    - LWT (Last Will & Testament) support
```

**Replace**:
- `self.mqtt_publish()` → `await mqtt_client.publish()`
- `self.mqtt_subscribe()` + `self.listen_event()` → `await mqtt_client.subscribe(topic, callback)`
- `self.get_plugin_config()` → Direct MQTT config from environment/config file

### 3. Configuration Management

**New file**: `qolsysgw/config.py` (enhance existing)

**Changes**:
- Add environment variable parsing
- Add YAML file loading (optional)
- Add validation using Pydantic or dataclasses
- Support both old `apps.yaml` format and new env var format for migration
- **User code validation**: Support both 4-digit and 6-digit codes (panels can be configured for either length)

**Configuration mapping**:
```python
# Environment Variables (example)
QOLSYS_PANEL_HOST=192.168.1.100
QOLSYS_PANEL_TOKEN=abc123...
QOLSYS_PANEL_USER_CODE=123456  # 4 or 6 digits supported

MQTT_HOST=mosquitto
MQTT_PORT=1883
MQTT_USERNAME=qolsysgw
MQTT_PASSWORD=secret
MQTT_BIRTH_TOPIC=homeassistant/status
MQTT_WILL_TOPIC=homeassistant/status
MQTT_BIRTH_PAYLOAD=online
MQTT_WILL_PAYLOAD=offline

HA_DISCOVERY_PREFIX=homeassistant
```

### 4. MQTT Listener Refactoring

**Changes to `mqtt/listener.py`**:
- Remove AppDaemon event system dependency
- Use direct callback registration with MQTT client
- Simplify `MqttQolsysEventListener` and `MqttQolsysControlListener`

**Before**: Relies on AppDaemon's `listen_event(callback, event='MQTT_MESSAGE')`
**After**: Direct subscription with `aiomqtt` async iteration

### 5. Logging Setup

**Changes**:
- Remove `AppDaemonLoggingHandler` and `AppDaemonLoggingFilter`
- Set up standard Python logging to stdout/stderr
- Use structured logging (JSON) for container environments
- Support log level from environment variable

**Implementation**: Will use standard `logging` module with plain text formatter and timestamps. Simple, readable format for debugging and development.

### 6. Task Management

**Replace**:
- `self.create_task()` → `asyncio.create_task()` or `TaskGroup.create_task()`

**Use Python 3.11+ `asyncio.TaskGroup`**:
```python
async with asyncio.TaskGroup() as tg:
    tg.create_task(qolsys_socket.listen())
    tg.create_task(qolsys_socket.keep_alive())
    tg.create_task(mqtt_client.run())
```

Benefits:
- Automatic task cleanup
- Better error handling
- Cancellation propagation

### 7. Docker Container Setup

**New file**: `Dockerfile`

**Requirements**:
- Python 3.13 base image
- Install dependencies from `requirements.txt`
- Non-root user for security
- Health check
- Proper signal handling

**Example structure**:
```dockerfile
FROM python:3.13-slim

# Create non-root user
RUN useradd -m -u 1000 qolsysgw

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application
COPY apps/qolsysgw /app/qolsysgw
WORKDIR /app

USER qolsysgw

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import sys; sys.exit(0)"  # TODO: Implement proper health check

CMD ["python", "-m", "qolsysgw"]
```

**New file**: `docker-compose.yaml` (example)

**New file**: `.dockerignore`

### 8. MQTT Birth/Will Configuration

**Implementation**:
- Set birth topic to `homeassistant/status` (default)
- Set will topic to `homeassistant/status` (default)
- Birth payload: `online`
- Will payload: `offline`
- QoS: 1 (at least once)
- Retain: True

**Usage in availability**:
- Link entity availability to this topic
- Ensures entities go unavailable when container stops

### 9. Home Assistant MQTT Discovery

**Current implementation** in `mqtt/updater.py` should remain mostly the same, but verify:
- Discovery prefix: `homeassistant` (default, configurable)
- Component: `alarm_control_panel` for partitions
- Component: `binary_sensor` for sensors
- Unique IDs are properly formatted
- Availability topics reference the birth/will topic

**Verify compatibility with Home Assistant 2025.11.1**:
- Check supported_features format
- Verify state payloads match expected values
- Ensure device registry entries are correct

### 10. Testing Strategy

**Update test structure**:
- Remove AppDaemon mocks
- Add MQTT client mocks
- Integration tests with real MQTT broker (using testcontainers)
- E2E tests with Docker Compose

**New test requirements**:
- `pytest-asyncio` for async tests
- `testcontainers` for MQTT broker in tests
- Mock Qolsys panel (already exists)

## Migration Path

### For Users

**Breaking changes**:
1. No longer requires AppDaemon
2. Configuration moves from `apps.yaml` to environment variables/config file
3. Runs as standalone container instead of AppDaemon app

**No migration guide**: Users wanting to upgrade must figure out configuration translation themselves or remain on v1.x AppDaemon version.

### Backward Compatibility

**Decision**: Clean break at v2.0.0
- Major version bump with breaking changes
- No migration guide
- No backward compatibility in codebase
- AppDaemon v1.x remains available but unmaintained

## File Structure Changes

```
qolsysgw-container/
├── Dockerfile
├── docker-compose.yaml
├── .dockerignore
├── requirements.txt (new, consolidate dependencies)
├── pyproject.toml (update for standalone app)
├── README.md (update installation/usage instructions)
├── qolsysgw/ (rename from apps/qolsysgw/)
│   ├── __init__.py
│   ├── __main__.py (new, entry point)
│   ├── main.py (new, application class)
│   ├── gateway.py (modified, remove AppDaemon)
│   ├── config.py (modified, add env var support)
│   ├── mqtt/
│   │   ├── client.py (new, aiomqtt wrapper)
│   │   ├── listener.py (modified)
│   │   ├── updater.py (minimal changes)
│   │   └── ...
│   └── qolsys/
│       └── ... (minimal changes)
├── tests/
│   ├── unit/
│   ├── integration/ (update mocks)
│   └── e2e/ (update for standalone container)
└── examples/
    ├── docker-compose.yaml (advanced: networks, volumes, dependencies)
    ├── .env.example
    └── config.yaml.example (optional YAML config)
```

## Dependencies

### New Dependencies (add to requirements.txt)
```
aiomqtt>=2.0.0  # Async MQTT client
pydantic>=2.0  # Configuration validation and settings management
python-dotenv>=1.0.0  # .env file support for development
pyyaml>=6.0  # Optional YAML config file support
```

### Keep Existing
- Python standard library (asyncio, logging, ssl, json)
- No external dependencies for Qolsys communication

### Remove
- appdaemon dependency (completely)

## Implementation Phases

### Phase 1: Core Refactoring
- [x] Create `requirements.txt` with dependencies (aiomqtt>=2.0.0, pydantic>=2.0, python-dotenv>=1.0.0, pyyaml>=6.0)
- [x] Create `.env.example` with all configuration variables
- [x] Create `qolsysgw/__init__.py` (if needed for package structure)
- [x] Create `qolsysgw/__main__.py` entry point
  - [x] Implement signal handlers (SIGTERM/SIGINT)
  - [x] Implement configuration loading
  - [x] Implement logging setup
  - [x] Implement main async event loop with TaskGroup
- [x] Create `qolsysgw/mqtt/client.py` aiomqtt wrapper
  - [x] Implement `connect()` method with LWT support
  - [x] Implement `disconnect()` method
  - [x] Implement `publish()` method
  - [x] Implement `subscribe()` method with callback support
  - [x] Implement auto-reconnect logic
  - [x] Implement message listener loop
- [x] Refactor `qolsysgw/config.py` for Pydantic models
  - [x] Create Pydantic models for Panel config
  - [x] Create Pydantic models for MQTT config
  - [x] Create Pydantic models for HA config
  - [x] Implement environment variable parsing
  - [x] Implement optional YAML config file loading
  - [x] Add configuration validation
- [x] Refactor `qolsysgw/gateway.py` to remove AppDaemon
  - [x] Remove `Mqtt` base class inheritance
  - [x] Remove AppDaemon logging handlers
  - [x] Replace `self.mqtt_publish()` with mqtt_client calls
  - [x] Replace `self.create_task()` with asyncio patterns
  - [x] Update initialization to accept config and mqtt_client
  - [x] Update `initialize()` to work without AppDaemon
  - [x] Update `terminate()` to work without AppDaemon
- [x] Update `qolsysgw/mqtt/listener.py` for direct MQTT
  - [x] Remove AppDaemon event system dependencies
  - [x] Refactor `MqttQolsysEventListener` for direct subscriptions
  - [x] Refactor `MqttQolsysControlListener` for direct subscriptions
  - [x] Update callback handling for aiomqtt
- [x] Update `qolsysgw/mqtt/updater.py` to work without AppDaemon
  - [x] Replace AppDaemon logging calls
  - [x] Update MQTT publish calls to use mqtt_client
  - [x] Verify discovery message format
- [x] Set up plain text logging with timestamps
  - [x] Configure root logger
  - [x] Add formatter with timestamps
  - [x] Support LOG_LEVEL environment variable
  - [x] Remove AppDaemon logging components
- [x] Create new unit tests for new components
  - [x] Create `tests/unit/mqtt/test_client.py` for MqttClient
    - [x] Test connect/disconnect
    - [x] Test publish
    - [x] Test subscribe with callbacks
    - [x] Test auto-reconnect logic
    - [x] Test LWT configuration
  - [x] Create `tests/unit/test_config.py` for new config system
    - [x] Test environment variable parsing
    - [x] Test YAML config loading
    - [x] Test config validation (Pydantic)
    - [x] Test config precedence (env vars override YAML)
    - [x] Test missing required fields
  - [x] Create `tests/unit/test_main.py` for __main__.py
    - [x] Test signal handler registration
    - [x] Test graceful shutdown
    - [x] Test configuration loading errors
- [x] Update existing unit tests to remove AppDaemon mocks
  - [x] Update `tests/unit/test_gateway.py` (no changes needed - tests still valid)
  - [x] Update `tests/unit/mqtt/test_listener.py`
  - [x] Update `tests/unit/mqtt/test_updater.py`
- [x] Run test suite: `pytest`
- [x] Verify all tests pass (85 passed, 4 skipped)
- [x] Run linter: `flake8`
- [x] Fix any linting issues

**Deliverable**: Runnable Python application that can be executed directly via `python -m qolsysgw` using `.env` file for configuration, with passing unit tests.

### Phase 2: Local Development & Testing
- [x] Update `.env.example` with comprehensive comments
- [ ] Create local `.env` file with real credentials (not committed)
- [ ] Test: Run `python -m qolsysgw` from command line
- [ ] Test: Run in PyCharm debugger
- [ ] Test: Verify MQTT connection establishes
- [ ] Test: Verify panel connection establishes
- [ ] Test: Verify sensors appear in Home Assistant
- [ ] Test: Verify partitions appear in Home Assistant
- [ ] Test: Send arm command from HA → verify panel receives
- [ ] Test: Send disarm command from HA → verify panel receives
- [ ] Test: Trigger sensor on panel → verify HA updates
- [ ] Test: Change partition state on panel → verify HA updates
- [ ] Test: Disconnect MQTT → verify auto-reconnect
- [ ] Test: Disconnect panel → verify auto-reconnect
- [ ] Test: Graceful shutdown with Ctrl+C
- [ ] Run test suite: `pytest`
- [ ] Run linter: `flake8`

**Deliverable**: Validated core functionality running natively in Python before containerization.

### Phase 3: Containerization
- [ ] Create `.dockerignore` file
- [ ] Create `Dockerfile`
  - [ ] Use python:3.13-slim base
  - [ ] Create non-root user
  - [ ] Copy and install requirements
  - [ ] Copy application code
  - [ ] Set working directory
  - [ ] Configure USER
  - [ ] Add HEALTHCHECK
  - [ ] Set CMD
- [ ] Create `docker-compose.yaml` example
  - [ ] Define qolsysgw service
  - [ ] Define networks
  - [ ] Define volumes (if needed)
  - [ ] Add environment variables
  - [ ] Add depends_on for MQTT
  - [ ] Configure restart policy
- [ ] Implement health check endpoint/script
- [ ] Test: Build Docker image locally
- [ ] Test: Run container with docker-compose
- [ ] Test: Verify same functionality as Phase 2
- [ ] Test: Container restart behavior
- [ ] Test: Health check reporting

**Deliverable**: Working Docker container with validated functionality.

### Phase 4: CI/CD & Container Testing
- [ ] Create `.github/workflows/container-build.yaml`
  - [ ] Configure trigger on tags only
  - [ ] Set up Docker Buildx
  - [ ] Configure GHCR authentication
  - [ ] Build multi-arch images (amd64, arm64)
  - [ ] Push to ghcr.io
  - [ ] Tag with version and 'latest'
- [ ] Create E2E test suite with Docker Compose
  - [ ] Test multi-container scenario
  - [ ] Test with external MQTT broker
  - [ ] Test with mock panel
- [ ] Test: Verify GitHub Actions workflow (dry run)
- [ ] Test: Health check functionality in container
- [ ] Test: Container restart and reconnection

**Deliverable**: Automated container builds and comprehensive container testing.

### Phase 5: Documentation
- [ ] Update `README.md`
  - [ ] Remove AppDaemon references
  - [ ] Add standalone container installation
  - [ ] Add docker-compose example
  - [ ] Document environment variables
  - [ ] Update prerequisites
  - [ ] Add troubleshooting section
- [ ] Update `CLAUDE.md`
  - [ ] Update architecture description
  - [ ] Remove AppDaemon references
  - [ ] Add new entry point documentation
  - [ ] Update build/run commands
  - [ ] Document new testing approach
- [ ] Create `examples/config.yaml.example` (optional YAML config)
- [ ] Create `examples/docker-compose.yaml` (advanced example)
- [ ] Create `examples/docker-compose-simple.yaml` (simple example)
- [ ] Document all environment variables in README
- [ ] Add upgrade notes in README

**Deliverable**: Complete documentation for v2.0.0.

### Phase 6: Release
- [ ] Update version to 2.0.0 in `pyproject.toml`
- [ ] Update version in `build_version.py` (if applicable)
- [ ] Create/update `CHANGELOG.md`
  - [ ] Document breaking changes
  - [ ] Document new features
  - [ ] Document migration notes
- [ ] Commit all changes
- [ ] Create git tag: `git tag -a v2.0.0 -m "Release v2.0.0"`
- [ ] Push tag: `git push origin v2.0.0`
- [ ] Verify GitHub Actions builds and publishes to GHCR
- [ ] Create GitHub Release
  - [ ] Use tag v2.0.0
  - [ ] Add release notes
  - [ ] Link to GHCR package
- [ ] Test: Pull image from GHCR
- [ ] Test: Run released image

**Deliverable**: Published v2.0.0 release on GHCR.

## Risks and Mitigations

### Risk 1: MQTT Reconnection Handling
**Risk**: AppDaemon handles MQTT reconnection automatically
**Mitigation**: Implement robust reconnection logic in `mqtt/client.py`, use aiomqtt's built-in reconnection support

### Risk 2: Breaking Changes for Users
**Risk**: All users must migrate configuration and deployment, no migration guide provided
**Mitigation**: v1.x AppDaemon version remains available in git history for users who need it. Breaking changes are clearly documented in v2.0.0 release notes.

### Risk 3: Testing Coverage
**Risk**: Major refactoring could introduce bugs
**Mitigation**: Maintain/improve test coverage, extensive integration testing before release

### Risk 4: State Synchronization on Reconnect
**Risk**: Panel state might drift during MQTT disconnection
**Mitigation**: Re-request panel state (INFO/SUMMARY) on MQTT reconnection

## Success Criteria

- [ ] Application runs standalone without AppDaemon
- [ ] Docker container builds and runs successfully
- [ ] MQTT connection with auto-reconnect works reliably
- [ ] Panel connection with auto-reconnect works reliably
- [ ] All sensors and partitions appear in Home Assistant
- [ ] Control commands from HA work (arm/disarm/trigger)
- [ ] Graceful shutdown on SIGTERM
- [ ] Test coverage ≥ 80%
- [ ] Documentation complete
- [ ] Container published to ghcr.io successfully

## Timeline Estimate

- Phase 1 (Core Refactoring): 12-16 hours
- Phase 2 (Local Development & Testing): 6-10 hours ⭐ *Real panel validation*
- Phase 3 (Containerization): 3-5 hours
- Phase 4 (CI/CD & Container Testing): 4-6 hours
- Phase 5 (Documentation): 4-6 hours
- Phase 6 (Release): 2-4 hours

**Total**: 31-47 hours of development time

⭐ **Phase 2 is critical** - this is where you validate core functionality against your real panel in PyCharm before adding Docker complexity.

## Ready to Implement

✅ **All design decisions finalized**. The plan is complete and ready for implementation.

### Implementation Approach

**Phase 1 (Core Refactoring)**: Build a runnable Python application
1. Create `requirements.txt` and `.env.example`
2. Create `qolsysgw/__main__.py` entry point
3. Create `qolsysgw/mqtt/client.py` aiomqtt wrapper
4. Refactor config, gateway, listeners for standalone operation
5. Set up logging

**Phase 2 (Local Testing)**: ⭐ **Validate with real panel in PyCharm**
- Run `python -m qolsysgw` with `.env` configuration
- Debug and fix issues against real hardware
- Ensure all functionality works before containerization

**Phase 3-6**: Containerize, automate, document, and release only after core is proven working.

### Final Notes

- No migration guide will be created
- v1.x remains in git history for users who need AppDaemon version
- v2.0.0 will be a complete rewrite focused on standalone Docker deployment
- GHCR will be the primary distribution method