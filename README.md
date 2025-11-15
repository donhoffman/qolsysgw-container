# Qolsys Gateway - `qolsysgw`

![build](https://github.com/donhoffman/qolsysgw-container/actions/workflows/build.yaml/badge.svg)
[![container build](https://github.com/donhoffman/qolsysgw-container/actions/workflows/container-build.yaml/badge.svg)](https://github.com/donhoffman/qolsysgw-container/pkgs/container/qolsysgw-container)
[![latest release](https://img.shields.io/github/v/release/donhoffman/qolsysgw-container?logo=github&sort=semver)](https://github.com/donhoffman/qolsysgw-container/releases)

Qolsys Gateway (`qolsysgw`) is a Python application that serves as a gateway between a Qolsys IQ Panel ([2][qolsys-panel-2], [2+][qolsys-panel-2-plus] or [4][qolsys-panel-4]) and [Home Assistant][hass].

**Key Features:**
- 🐳 **Standalone Docker container** - runs alongside your Home Assistant installation
- 🔄 **Automatic MQTT discovery** - sensors and partitions appear automatically in Home Assistant
- 🔐 **Secure communication** - encrypted connection to your Qolsys panel
- 🎯 **Full control** - arm, disarm, and trigger your alarm from Home Assistant
- 📡 **Real-time updates** - instant state synchronization between panel and Home Assistant
- 🏗️ **Multi-architecture support** - runs on amd64 and arm64 (Raspberry Pi compatible)

Qolsys Gateway connects to your Qolsys Panel using the Control4 protocol and publishes all partitions, sensors, and state changes to [Home Assistant via MQTT][hass-mqtt]. It leverages [MQTT discovery][hass-mqtt-discovery] to automatically create entities in Home Assistant, while providing full bidirectional control for arming, disarming, and triggering your alarm system.

## About This Fork

This project is a fork of the original [qolsysgw by XaF](https://github.com/XaF/qolsysgw), redesigned to run as a standalone Docker container. While the original project integrates with AppDaemon for users who prefer that ecosystem, this fork takes a different approach:

- **Standalone architecture** - runs as an independent container without external dependencies
- **Native async Python** - built on modern Python 3.13+ with native asyncio
- **Container-first design** - optimized for Docker and container orchestration
- **Simplified deployment** - configure via environment variables, deploy with Docker Compose

Both projects share the same goal of integrating Qolsys panels with Home Assistant, but serve different deployment preferences.


## Table of Contents

- [How It Works](#how-it-works)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Installation](#installation)
  - [Pull from GitHub Container Registry](#pull-from-github-container-registry)
  - [Using Docker Compose](#using-docker-compose)
  - [Using Docker Run](#using-docker-run)
- [Configuration](#configuration)
  - [Configuring your Qolsys IQ Panel](#configuring-your-qolsys-iq-panel)
  - [Required Environment Variables](#required-environment-variables)
  - [Optional Environment Variables](#optional-environment-variables)
    - [Panel Configuration](#panel-configuration)
    - [Home Assistant Configuration](#home-assistant-configuration)
    - [MQTT Configuration](#mqtt-configuration)
- [Troubleshooting](#troubleshooting)
- [Other Documentation](#other-documentation)
- [Acknowledgements and Thanks](#acknowledgements-and-thanks)


## How It Works

Qolsys Gateway is an [async Python application][asyncio] that runs three concurrent workflows:

### 1. Panel Communication
- Connects to your Qolsys Panel via the Control4 protocol (SSL/TLS)
- Requests initial state (partitions, sensors, status) on connection
- Listens for real-time events from the panel (sensor triggers, state changes, etc.)
- Sends keep-alive messages every 4 minutes to maintain the connection
- Automatically reconnects if the connection is lost

### 2. MQTT Publishing
- Publishes panel events and state changes to MQTT topics
- Uses Home Assistant's MQTT discovery to automatically create entities
- Updates sensor states, partition status, and device information in real-time
- Publishes availability status (online/offline) with Last Will and Testament (LWT)

### 3. MQTT Control Listener
- Subscribes to control topics for commands from Home Assistant
- Processes arm/disarm/trigger commands from `alarm_control_panel` entities
- Validates user codes and session tokens for security
- Sends validated commands to the Qolsys Panel
- Detects Home Assistant restarts and republishes entity configurations


## Requirements

- **Qolsys IQ Panel**: Panel 2 or 2+ (software version 2.5.3 or greater), or Panel 4 (software version 4.1 or greater). You must have the **dealer code** (defaults to `2222`) to enable the Control4 interface. In some cases, the _installer code_ (defaults to `1111`) might be sufficient, but the required menus may not be visible.

- **MQTT Broker**: A working MQTT broker (e.g., Mosquitto) accessible from both Home Assistant and the Qolsys Gateway container.

- **Docker**: Docker and Docker Compose for running the containerized application.

- **Home Assistant**: With the MQTT integration configured.

- **Network Access**: The Qolsys Gateway container must be able to reach both your Qolsys Panel and MQTT broker on your network.

**Security Notice**: This application is not part of the core of Home Assistant and is not officially supported. Setting up Qolsys Gateway requires enabling the Control4 protocol on your Qolsys Panel, which involves network-accessible communication with your alarm system. Ensure you understand the security implications and take appropriate precautions (firewall rules, network segmentation, etc.). Use at your own risk.


## Quick Start

Get up and running quickly with Docker Compose:

```yaml
version: '3.8'

services:
  qolsysgw:
    image: ghcr.io/donhoffman/qolsysgw-container:latest
    container_name: qolsysgw
    network_mode: host
    restart: unless-stopped
    environment:
      # Required: Panel connection
      QOLSYS_PANEL_HOST: "192.168.1.100"  # Your panel's IP address
      QOLSYS_PANEL_TOKEN: "your_secure_token_here"

      # Required: MQTT connection
      MQTT_HOST: "mosquitto"  # Your MQTT broker hostname

      # Optional: MQTT authentication (recommended)
      MQTT_USERNAME: "qolsysgw"
      MQTT_PASSWORD: "your_mqtt_password"

      # Optional: Panel user code (for disarming without entering code in HA)
      QOLSYS_PANEL_USER_CODE: "123456"
```

See [Configuration](#configuration) below for all available options.


## Installation

Qolsys Gateway is distributed as a Docker container via GitHub Container Registry (GHCR).

### Pull from GitHub Container Registry

```bash
docker pull ghcr.io/donhoffman/qolsysgw-container:latest
```

**Available tags:**
- `latest` - Latest stable release
- `2.0.0` - Specific version
- `2.0` - Latest 2.0.x release
- `2` - Latest 2.x release

### Using Docker Compose

Create a `docker-compose.yml` file (see [Quick Start](#quick-start) above for a complete example) and run:

```bash
docker compose up -d
```

**View logs:**
```bash
docker compose logs -f qolsysgw
```

**Stop the container:**
```bash
docker compose down
```

### Using Docker Run

```bash
docker run -d \
  --name qolsysgw \
  --network host \
  --restart unless-stopped \
  -e QOLSYS_PANEL_HOST="192.168.1.100" \
  -e QOLSYS_PANEL_TOKEN="your_secure_token_here" \
  -e MQTT_HOST="mosquitto" \
  -e MQTT_USERNAME="qolsysgw" \
  -e MQTT_PASSWORD="your_mqtt_password" \
  ghcr.io/donhoffman/qolsysgw-container:latest
```

**Note:** Using `--network host` is recommended as it allows the container to discover your panel and MQTT broker easily. If you prefer bridge networking, ensure the container can reach both your panel and MQTT broker.


## Configuration

Qolsys Gateway is configured using environment variables. You can set these in:
- A `.env` file (recommended for Docker Compose)
- `docker-compose.yml` environment section
- Direct `-e` flags with `docker run`

See [`.env.example`](./.env.example) for a complete reference with detailed comments on all options.


### Configuring your Qolsys IQ Panel

If you already have the Control4 token for your Qolsys IQ Panel, you can
skip that step. If you do not understand what that sentence is about, you
definitely need to go through that step.

Qolsys Gateway communicates with your Qolsys Panel using a protocol that
exists for communications with Control4 automation. That protocol is not
enabled on your Qolsys Panel by default, so we will need to enable it and
note the token that will be provided to us.

To enable the feature and get your secure token, you will need to:

1. <details><summary>Connect your Qolsys Panel to your WiFi network (if not already done)</summary>

   1. Swipe down from the top menu bar and select `Settings`.
   2. Touch `Advanced Settings` and use either the _installer_ code or
      the _dealer_ code (you might have access with the main user code, too).
   3. Touch `Wi-Fi`.
   4. Check the `Enable Wi-Fi` box if not already active.
   5. Available networks will appear in a list.
   6. Touch the desired network and use the keyboard to type the password (if required).

   <p></p>

   <p align="center">
     <img src="./docs/images/qolsys-connecting-to-wifi.png"
          alt="Qolsys documentation to connect to WiFi" width="738" />
   </p>

   </details>

1. <details><summary>Enable 3rd party connections</summary>

   1. Swipe down from the top menu bar and select `Settings`.
   2. Touch `Advanced Settings` and use the _dealer_ code (you **might** have
      access with the _installer_ code, too).
   3. Touch `Installation`.
   4. Touch `Devices`.
   5. Touch `Wi-Fi Devices`.
   6. Touch `3rd Party Connections`.
   7. Check the `Control4` box to enable 3rd Party Connections.
   8. The panel will reboot in order to apply the change.
   9. Come back to the same menu once the reboot is done.
   10. Touch `Reveal secure token` and note the token that the panel is
       providing you, we will need it to configure Qolsys Gateway.
   11. If you ever leak that token, come back to this menu and touch
       `Regenerate secure token` in order to make sure that nobody can
       get access to control your alarm system.

   <p></p>

   <p align="center">
     <img src="./docs/images/qolsys-3rd-party-connections.png"
          alt="Qolsys documentation for 3rd party connections" width="738">
   </p>

   </details>


### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `QOLSYS_PANEL_HOST` | IP address or hostname of your Qolsys Panel | `192.168.1.100` |
| `QOLSYS_PANEL_TOKEN` | Secure token from Control4 interface (see [Panel Configuration](#configuring-your-qolsys-iq-panel)) | `abc123...` |
| `MQTT_HOST` | MQTT broker hostname or IP address | `mosquitto` or `192.168.1.50` |

### Optional Environment Variables

#### Panel Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `QOLSYS_PANEL_PORT` | Auto-detect | Panel port (usually 12345 or 12346) |
| `QOLSYS_PANEL_MAC` | Auto-detect | Panel MAC address (format: `AA:BB:CC:DD:EE:FF`) |
| `QOLSYS_PANEL_USER_CODE` | None | User code for arming/disarming (4 or 6 digits) |
| `QOLSYS_PANEL_UNIQUE_ID` | `qolsys_panel` | Unique ID for this panel (for multiple panels) |
| `QOLSYS_PANEL_DEVICE_NAME` | `Qolsys Panel` | Friendly name in Home Assistant |

#### Arming Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `QOLSYS_ARM_AWAY_EXIT_DELAY` | Panel default | Exit delay in seconds for arm away (0 = instant) |
| `QOLSYS_ARM_STAY_EXIT_DELAY` | Panel default | Exit delay in seconds for arm stay (0 = instant) |
| `QOLSYS_ARM_AWAY_BYPASS` | Panel default | Auto-bypass open sensors when arming away (`true`/`false`) |
| `QOLSYS_ARM_STAY_BYPASS` | Panel default | Auto-bypass open sensors when arming stay (`true`/`false`) |
| `QOLSYS_ARM_TYPE_CUSTOM_BYPASS` | `arm_away` | Arm mode for custom bypass (`arm_away` or `arm_stay`) |

#### MQTT Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MQTT_PORT` | `1883` | MQTT broker port (1883 for plain, 8883 for TLS) |
| `MQTT_USERNAME` | None | MQTT authentication username |
| `MQTT_PASSWORD` | None | MQTT authentication password |
| `MQTT_QOS` | `1` | MQTT Quality of Service level (0, 1, or 2) |
| `MQTT_RETAIN` | `true` | Retain MQTT messages (`true`/`false`) |

#### Home Assistant Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HA_DISCOVERY_PREFIX` | `homeassistant` | Home Assistant MQTT discovery prefix |
| `HA_CHECK_USER_CODE` | `true` | Validate codes in HA vs sending to panel (`true`/`false`) |
| `HA_USER_CODE` | None | Separate code for HA validation (if different from panel code) |
| `HA_CODE_ARM_REQUIRED` | `false` | Require code to arm (`true`/`false`) |
| `HA_CODE_DISARM_REQUIRED` | `false` | Require code to disarm (`true`/`false`) |
| `HA_CODE_TRIGGER_REQUIRED` | `false` | Require code to trigger alarm (`true`/`false`) |
| `HA_STATUS_TOPIC` | `{prefix}/status` | Topic where HA publishes status |
| `HA_STATUS_ONLINE_PAYLOAD` | `online` | Payload indicating HA is online |

#### Sensor Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `QOLSYS_SENSOR_DEFAULT_DEVICE_CLASS` | `safety` | Default device class for unmapped sensors |
| `QOLSYS_SENSOR_ENABLE_STATIC_BY_DEFAULT` | `false` | Enable static sensors (keypads, sirens) by default |

#### Trigger Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `QOLSYS_TRIGGER_DEFAULT_COMMAND` | None | Default trigger type: `TRIGGER`, `TRIGGER_FIRE`, `TRIGGER_POLICE`, `TRIGGER_AUXILIARY` |

#### Logging Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

### Example Configuration

**.env file:**
```bash
# Required
QOLSYS_PANEL_HOST=192.168.1.100
QOLSYS_PANEL_TOKEN=your_token_here
MQTT_HOST=mosquitto

# Optional - MQTT Authentication
MQTT_USERNAME=qolsysgw
MQTT_PASSWORD=secure_password

# Optional - Panel user code (recommended)
QOLSYS_PANEL_USER_CODE=123456

# Optional - Arming configuration
QOLSYS_ARM_AWAY_EXIT_DELAY=0  # Instant arm when triggered from automations
QOLSYS_ARM_STAY_EXIT_DELAY=30

# Optional - Logging
LOG_LEVEL=DEBUG  # For troubleshooting
```

**docker-compose.yml:**
```yaml
services:
  qolsysgw:
    image: ghcr.io/donhoffman/qolsysgw-container:latest
    env_file: .env  # Load from .env file
    # Or specify directly:
    # environment:
    #   QOLSYS_PANEL_HOST: "192.168.1.100"
    #   QOLSYS_PANEL_TOKEN: "your_token"
    #   MQTT_HOST: "mosquitto"
    network_mode: host
    restart: unless-stopped
```


## Troubleshooting

### Container won't start
- **Check logs**: `docker compose logs qolsysgw`
- **Verify required variables**: Ensure `QOLSYS_PANEL_HOST`, `QOLSYS_PANEL_TOKEN`, and `MQTT_HOST` are set
- **Network connectivity**: Container must reach both panel and MQTT broker

### Can't connect to panel
- **Verify token**: Token must match what's shown on panel under Control4 settings
- **Check network**: Panel must be reachable from container (`ping` test from host)
- **Port conflicts**: Ensure port 12345/12346 not blocked by firewall
- **Panel reboot**: If Control4 was just enabled, panel may need reboot

### Entities not appearing in Home Assistant
- **MQTT integration**: Ensure HA's MQTT integration is configured and connected
- **Discovery prefix**: Verify `HA_DISCOVERY_PREFIX` matches HA's MQTT discovery prefix (default: `homeassistant`)
- **Check MQTT**: Use MQTT explorer to verify messages are being published
- **HA restart**: Sometimes HA needs restart to pick up new MQTT discovery messages

### Sensors showing unavailable
- **Panel connection**: Check if gateway is connected to panel (check logs)
- **MQTT retain**: If `MQTT_RETAIN=false`, states may not persist across HA restarts
- **Panel response**: Some sensors only update when triggered

### Can't arm/disarm from Home Assistant
- **User code**: If no `QOLSYS_PANEL_USER_CODE` set, you must provide code in HA
- **Code requirements**: Check `HA_CODE_*_REQUIRED` settings match your preferences
- **Session token**: Gateway creates session tokens to validate HA commands (check logs for errors)

### Container keeps restarting
- **Check logs**: `docker compose logs qolsysgw` for error messages
- **Invalid config**: Verify all environment variables are correctly formatted
- **MQTT broker**: Ensure MQTT broker is running and accessible

### Enable DEBUG logging
```bash
# In .env file
LOG_LEVEL=DEBUG
```

Then restart container:
```bash
docker compose restart qolsysgw
docker compose logs -f qolsysgw
```


## Other documentation

- [The known Qolsys Panel interactions](./docs/qolsys-panel-interactions.md)
- [Qolsys Gateway's control commands](./docs/qolsysgw-control-commands.md)
- [Qolsys Gateway's entities](./docs/qolsysgw-entities.md)


## Acknowledgements and Thanks

This project would not exist without the incredible work and contributions of many individuals in the Home Assistant community.

### Original qolsysgw Project

Deepest thanks to **[XaF (Raphaël Beamonte)](https://github.com/XaF)** for creating the [original qolsysgw project](https://github.com/XaF/qolsysgw). Their exceptional work on the AppDaemon-based gateway provided the foundation, architecture, and core functionality that made this containerized fork possible. The quality of their code, documentation, and thoughtful design decisions made it a pleasure to build upon.

### Home Assistant Community

Tremendous gratitude to the [Home Assistant Community Forum](https://community.home-assistant.io/) members who pioneered the integration of Qolsys panels with Home Assistant. The [original discussion thread][hass-community-thread] was instrumental in discovering the Control4 interface, documenting the protocol, and sharing countless hours of experimentation and testing. Special thanks to all the community members who contributed their time, panels, and patience to make this integration possible.

### Inspiration and Foundation

Deep appreciation to **[@roopesh](https://github.com/roopesh)** for the [ad-qolsys][ad-qolsys] project, which served as an early inspiration and proof of concept for Qolsys panel integration with Home Assistant. Their pioneering work demonstrated what was possible and inspired others to build upon it.

### The Broader Community

Thank you to the entire Home Assistant ecosystem - the core developers, integration maintainers, and countless contributors who have built such an incredible platform. Special thanks to the MQTT integration maintainers and the AppDaemon team for providing the tools that make projects like this possible.

---

**Note**: This containerized fork represents a different architectural approach to the same goal. All credit for the original concept, protocol implementation, and core functionality belongs to the contributors mentioned above.


<!--
List of links used in that page, sorted alphabetically by tag
-->
[ad-qolsys]: https://github.com/roopesh/ad-qolsys
[appdaemon-docker]: https://hub.docker.com/r/acockburn/appdaemon/
[appdaemon-hass-plugin]: https://appdaemon.readthedocs.io/en/latest/CONFIGURE.html#configuration-of-the-hass-plugin
[appdaemon-install]: https://appdaemon.readthedocs.io/en/latest/INSTALL.html
[appdaemon-mqtt-plugin]: https://appdaemon.readthedocs.io/en/latest/CONFIGURE.html#configuration-of-the-mqtt-plugin
[appdaemon]: https://github.com/AppDaemon/appdaemon
[asyncio]: https://docs.python.org/3/library/asyncio.html
[hacs-install]: https://hacs.xyz/docs/use
[hacs-pr]: https://github.com/hacs/default/pull/1173
[hass-community-thread]: https://community.home-assistant.io/t/qolsys-iq-panel-2-and-3rd-party-integration/231405
[hass-install]: https://www.home-assistant.io/installation/
[hass-mqtt-broker]: https://www.home-assistant.io/docs/mqtt/broker
[hass-mqtt-discovery]: https://www.home-assistant.io/docs/mqtt/discovery/
[hass-mqtt]: https://www.home-assistant.io/integrations/mqtt/
[hass]: https://www.home-assistant.io/
[mqtt-docker]: https://hub.docker.com/_/eclipse-mosquitto
[qolsys-panel-2]: https://qolsys.com/iq-panel-2/
[qolsys-panel-2-plus]: https://qolsys.com/iq-panel-2-plus/
[qolsys-panel-4]: https://qolsys.com/iq-panel-4/
[roopesh]: https://github.com/roopesh
