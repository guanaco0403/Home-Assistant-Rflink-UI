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
- 📻 **Custom Commands**: Send any raw RF command using the `radio_frequency.send_command` service
- 🟢 **Connection Sensor**: Includes a binary sensor to monitor the gateway's connection status in real-time

---

## ⚠️ Warning
- The entity unique ID is generated using the hardware's protocol and ID (e.g., `rflink_switch_Unitec_1a4a_4`).
- If you remove a device from the integration's Options, the associated entity will be dynamically removed from Home Assistant.
- This integration is built as a complete replacement for the legacy `rflink` component. **Do not run both simultaneously on the same serial port !!!**

---

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

## 🛠 Service: `radio_frequency.send_command`

You can manually send any raw RF command through the gateway.

### Example:

```yaml
service: radio_frequency.send_command
target:
  entity_id: radio_frequency.transmitter
data:
  protocol: "Unitec"
  command: "1a4a;4;ON"
```

## 🧪 Requirements

- Home Assistant 2026.5.4 or newer
- Python 3.12+
- pyserial-asyncio-fast>=0.11 (automatically installed)

## 🏷 Supported Platforms

- `sensor` – For temperature, humidity, and other read-only RF signals
- `switch` – For writable on/off RF plugs and lights
- `binary_sensor` – For monitoring the gateway connection status
- `radio_frequency` – For the main gateway entity that transmits custom commands

## 📁 File Structure

```text
custom_components/
└── rflink_ui/
    ├── __init__.py
    ├── manifest.json
    ├── sensor.py
    ├── switch.py
    ├── binary_sensor.py
    ├── radio_frequency.py
    ├── config_flow.py
    └── translations/
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
