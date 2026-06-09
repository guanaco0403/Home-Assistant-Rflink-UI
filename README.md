# 🏠 Home Assistant RFLink UI

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

## 🔌 Overview

**Home-Assistant-RFLink-UI** is a modern, fully UI-driven custom [Home Assistant](https://www.home-assistant.io) integration for Arduino RFLink gateways. Unlike the legacy YAML-based RFLink integration, this component is configured entirely through the Home Assistant UI and supports dynamic discovery of devices.

This integration uses the `serial_asyncio` library for fast, non-blocking communication and is designed to bring RFLink into the modern era of Home Assistant.

---



## ✨ Features

- 📡 **Connects to any standard Arduino RFLink gateway** via USB/Serial
- 🔍 **Auto-Discovery Mode**: Discovers recently received signals and lets you add them directly from a dropdown in the UI!
- ✍️ **Manual Addition**: Add your switches and sensors manually if you already know their protocol and IDs
- 🔄 **Async Serial Polling**: Non-blocking connection with automatic background reconnects and keep-alive pings
- 📻 **Custom Commands**: Send any raw RF command using the rflink_ui.send_command service.
- 🟢 **Connection Sensor**: Includes a binary sensor to monitor the gateway's connection status in real-time
- 🧪 **Packet Simulation**: Built-in service (rflink_ui.simulate_packet) to inject mock RF packets for easy testing and debugging without physical hardware.

---

## 🏷 Supported Platforms & Entities

- **`sensor`** — Creates dedicated `Temperature` (in °C), `Humidity` (in %), and `Battery` status entities for numerical climate sensors (e.g., Oregon Scientific, Cresta). Extra fields like wind or pressure are stored as attributes on these entities.
- **`switch`** — Creates control entities for writable RF outlets, relays, and lights (e.g., Kaku, Unitec, Chacon) so you can trigger them or sync their state with physical remotes.
- **`binary_sensor`** — Covers status monitoring:
  - **Gateway Connection**: A connectivity sensor tracking the serial port connection to the RFLink gateway.
  - **RF Devices**: Any binary state sensor (e.g., PIR motion detectors, door/window opening contacts, smoke detectors, water leak sensors, doorbells). Fully supports configurable `device_class` and `off_delay` for trigger-only sensors.
- **`radio_frequency`** *(New in Home Assistant 2026.5.0)* — Exposes the main gateway transmitter entity to allow broadcasting custom RF payloads using standard actions.

## ⚠️ Warning
- The entity unique ID is generated using the hardware's protocol and ID (e.g., `rflink_switch_Unitec_1a4a_4`).
- If you remove a device from the integration's Options, the associated entity will be dynamically removed from Home Assistant.
- This integration is built as a complete replacement for the legacy `rflink` component. **Do not run both simultaneously on the same serial port !!!**

---

## 🧪 Requirements

- **Home Assistant 2026.5.4 or newer**
- Python 3.12+
- pyserial-asyncio-fast>=0.11 (automatically installed)

## 📦 Installation

### Option 1: HACS (Recommended for Users)
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?repository=Home-Assistant-Rflink-UI&owner=guanaco0403&category=integration)

1. Go to **HACS > Integrations > Custom repositories**
2. Add this repo URL: `https://github.com/guanaco0403/Home-Assistant-Rflink-UI`
3. Select category: **Integration**
4. Click **Add**
5. Install the `RFLink UI` integration
6. Restart Home Assistant

### Option 2: Manual

1. Download the latest release from GitHub
2. Extract and copy the `rflink_ui` folder into: `/config/custom_components/`
3. Restart Home Assistant

---

## ⚙️ Configuration

### Setup via Home Assistant UI

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **RFLink UI**
3. Select your serial port from the dropdown (e.g., `/dev/ttyUSB0` or `COM3`)
4. Submit to connect!

### Adding Devices (Options Flow)

Once configured, click **Configure** on the integration card to:
- **Add recently detected device**: View signals picked up in the last few minutes and quickly map them to an entity.
- **Add device manually**: Manually type in the Protocol and ID.
- **Remove device**: Delete an existing device from the integration.

---

## 🛠 Action: `rflink_ui.send_command`

You can manually send any raw RF command through the gateway.

### Example:

```yaml
action: rflink_ui.send_command
target:
  entity_id: radio_frequency.rflink_com3_transmitter  # Replace with your actual transmitter entity ID (e.g. rflink_dev_ttyusb0_transmitter)
data:
  protocol: "Unitec"
  command: "1a4a;4;ON"
```

## 🛠 Action: `rflink_ui.simulate_packet`

You can simulate receiving a raw RFLink packet string in the integration. This is highly useful for testing or auto-discovering devices without physical hardware.

### Example:

```yaml
action: rflink_ui.simulate_packet
data:
  packet: "20;01;Kaku;ID=1234abcd;SWITCH=1;CMD=ON;"
```

## 📌 Integration Type & Quality

- Integration Type: hub
- Quality Scale: bronze
- IoT Class: local_push

## 🧑‍💻 Code Owner

- @guanaco0403

## 🪪 License

This project is licensed under the MIT License.

## 📢 Contribute

Pull requests are welcome! If you want to improve signal parsing, add support for more sensor types (like wind/rain), or enhance the config flow — contributions are greatly appreciated.

## 🧪 Testing & Development

This repository includes a dedicated test runner (`scripts/test_runner.py`) that automatically sets up an isolated virtual environment (`.venv_ha_test`), installs the specified Home Assistant version, and configures dependencies.

### Running the Test Runner

* **Run Automated Tests** (default action)
  ```bash
  # Standard command
  python3.14 scripts/test_runner.py

  # On Windows (using the Python Launcher)
  py -3.14 scripts/test_runner.py
  ```

* **Run Live Local Home Assistant** (runs a local HA instance preloaded with the integration)
  ```bash
  # Standard command
  python3.14 scripts/test_runner.py --run

  # On Windows (using the Python Launcher)
  py -3.14 scripts/test_runner.py --run
  ```
  Once the server starts, navigate to `http://localhost:8123` in your browser.

### Advanced Options

| Flag | Description | Default |
| :--- | :--- | :--- |
| `-v`, `--version` | Target Home Assistant version (or `"latest"`) | `2026.5.0` |
| `--port` | Port to run the live Home Assistant instance on | `8123` |
| `--clean` | Force re-creation of the virtual environment | |

*Example (testing a different HA version):*
```bash
py -3.14 scripts/test_runner.py --version 2026.6.0
```

### Code Style & Linting

We use [Ruff](https://beta.ruff.rs/docs/) and [Black](https://github.com/psf/black) to enforce style consistency and linting checks.

* **Lint Checks (Ruff)**
  ```bash
  # Check for issues
  ruff check custom_components/

  # Auto-fix fixable issues
  ruff check custom_components/ --fix
  ```

* **Code Formatting (Black)**
  ```bash
  # Check formatting
  black --check custom_components/

  # Auto-format files
  black custom_components/
  ```


