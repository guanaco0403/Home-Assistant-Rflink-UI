"""Config flow for RFLink Transmitter integration."""

from typing import Any

import serial
import serial.tools.list_ports
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PORT
from homeassistant.core import callback

from . import DOMAIN


class RFLinkTransmitterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RFLink Transmitter."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return RFLinkOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            port = user_input[CONF_PORT]
            try:
                # Do this in an executor to avoid blocking the event loop
                await self.hass.async_add_executor_job(self._test_serial_port, port)
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"RFLink ({port})", data=user_input
                )

        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        port_list = [port.device for port in ports]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PORT, default=port_list[0] if port_list else ""
                    ): (vol.In(port_list) if port_list else str),
                }
            ),
            errors=errors,
        )

    def _test_serial_port(self, port: str) -> None:
        """Test if the serial port can be opened."""
        with serial.Serial(port, 57600, timeout=1):
            pass


class RFLinkOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.options = dict(config_entry.options)
        self.options["switches"] = dict(self.options.get("switches", {}))
        self.options["sensors"] = dict(self.options.get("sensors", {}))
        self.options["binary_sensors"] = dict(self.options.get("binary_sensors", {}))
        self._temp_device_id = None
        self._temp_name = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_learned", "add_manual", "modify", "remove"],
        )

    async def async_step_add_learned(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add a recently seen device."""
        errors: dict[str, str] = {}
        data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)

        if user_input is not None:
            selection = user_input.get("device_id")
            if selection == "clear":
                if data:
                    data.recent_unknown_devices.clear()
                return await self.async_step_add_learned()
            elif selection == "refresh":
                return await self.async_step_add_learned()
            else:
                name = user_input.get("name")
                if not name:
                    errors["name"] = "missing_name"
                else:
                    if selection.startswith("[Switch] "):
                        dev_id = selection.replace("[Switch] ", "")
                        self.options["switches"][dev_id] = name
                        return self.async_create_entry(title="", data=self.options)
                    elif selection.startswith("[Binary Sensor] "):
                        dev_id = selection.replace("[Binary Sensor] ", "")
                        self._temp_device_id = dev_id
                        self._temp_name = name
                        return await self.async_step_binary_sensor_options()
                    elif selection.startswith("[Sensor] "):
                        dev_id = selection.replace("[Sensor] ", "")
                        self.options["sensors"][dev_id] = name
                        return self.async_create_entry(title="", data=self.options)

        devices_dict = {
            "refresh": "Refresh list",
            "clear": "Clear signals",
        }

        has_devices = False
        if data:
            configured_switches = self.options.get("switches", {})
            configured_sensors = self.options.get("sensors", {})
            configured_binary_sensors = self.options.get("binary_sensors", {})
            for dev_id, info in data.recent_unknown_devices:
                if (
                    dev_id not in configured_switches
                    and dev_id not in configured_sensors
                    and dev_id not in configured_binary_sensors
                ):
                    has_devices = True
                    if info["type"] == "switch":
                        key_sw = f"[Switch] {dev_id}"
                        key_bs = f"[Binary Sensor] {dev_id}"
                        devices_dict[key_sw] = f"{key_sw}"
                        devices_dict[key_bs] = f"{key_bs}"
                    else:
                        key = f"[Sensor] {dev_id}"
                        devices_dict[key] = f"{key}"

        if not has_devices:
            errors["base"] = "no_devices_found"

        return self.async_show_form(
            step_id="add_learned",
            data_schema=vol.Schema(
                {
                    vol.Required("device_id", default="refresh"): vol.In(devices_dict),
                    vol.Optional("name"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_add_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add a device manually."""
        if user_input is not None:
            dev_id = user_input["device_id"]
            name = user_input["name"]
            dev_type = user_input["device_type"]

            if dev_type in ["Switch", "Interrupteur"]:
                self.options["switches"][dev_id] = name
                return self.async_create_entry(title="", data=self.options)
            elif dev_type in ["Binary Sensor", "Capteur binaire"]:
                self._temp_device_id = dev_id
                self._temp_name = name
                return await self.async_step_binary_sensor_options()
            else:
                self.options["sensors"][dev_id] = name
                return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="add_manual",
            data_schema=vol.Schema(
                {
                    vol.Required("device_type", default="Switch"): vol.In(
                        ["Switch", "Sensor", "Binary Sensor", "Interrupteur", "Capteur", "Capteur binaire"]
                    ),
                    vol.Required("device_id"): str,
                    vol.Required("name"): str,
                }
            ),
        )

    async def async_step_binary_sensor_options(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure binary sensor specific options."""
        if user_input is not None:
            device_class = user_input.get("device_class")
            off_delay = user_input.get("off_delay")

            # Save to options dict
            self.options["binary_sensors"][self._temp_device_id] = {
                "name": self._temp_name,
                "device_class": device_class if device_class != "none" else None,
                "off_delay": off_delay if off_delay else None,
            }
            return self.async_create_entry(title="", data=self.options)

        # List of binary sensor device classes supported by Home Assistant
        try:
            from homeassistant.components.binary_sensor import BinarySensorDeviceClass
            device_classes = ["none"] + [c.value for c in BinarySensorDeviceClass]
        except ImportError:
            device_classes = [
                "none", "battery", "co", "cold", "connectivity", "door", "garage_door",
                "gas", "heat", "light", "lock", "moisture", "motion", "moving",
                "occupancy", "opening", "plug", "power", "presence", "problem",
                "running", "safety", "smoke", "sound", "tamper", "update", "vibration",
                "window"
            ]

        return self.async_show_form(
            step_id="binary_sensor_options",
            data_schema=vol.Schema(
                {
                    vol.Optional("device_class", default="none"): vol.In(device_classes),
                    vol.Optional("off_delay"): vol.All(
                        vol.Coerce(int), vol.Range(min=1)
                    ),
                }
            ),
        )

    async def async_step_modify(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Modify a device ID."""
        configured_switches = self.options.get("switches", {})
        configured_sensors = self.options.get("sensors", {})
        configured_binary_sensors = self.options.get("binary_sensors", {})

        all_devices = {}
        for dev_id, name in configured_switches.items():
            all_devices[f"[Switch] {dev_id}"] = f"{name} ({dev_id})"
        for dev_id, config in configured_binary_sensors.items():
            name = config.get("name") if isinstance(config, dict) else config
            all_devices[f"[Binary Sensor] {dev_id}"] = f"{name} ({dev_id})"
        for dev_id, name in configured_sensors.items():
            all_devices[f"[Sensor] {dev_id}"] = f"{name} ({dev_id})"

        if not all_devices:
            return self.async_abort(reason="no_configured_devices")

        errors = {}

        if user_input is not None:
            selection = user_input["device_id"]
            new_dev_id = user_input["new_device_id"]

            from homeassistant.helpers import (
                device_registry as dr,
                entity_registry as er,
            )

            dev_reg = dr.async_get(self.hass)
            ent_reg = er.async_get(self.hass)

            device_type = None
            if selection.startswith("[Switch] "):
                old_dev_id = selection.replace("[Switch] ", "")
                name = self.options["switches"].pop(old_dev_id, None)
                if name:
                    self.options["switches"][new_dev_id] = name
                    device_type = "switch"
            elif selection.startswith("[Binary Sensor] "):
                old_dev_id = selection.replace("[Binary Sensor] ", "")
                config = self.options["binary_sensors"].pop(old_dev_id, None)
                if config:
                    self.options["binary_sensors"][new_dev_id] = config
                    device_type = "binary_sensor"
            elif selection.startswith("[Sensor] "):
                old_dev_id = selection.replace("[Sensor] ", "")
                name = self.options["sensors"].pop(old_dev_id, None)
                if name:
                    self.options["sensors"][new_dev_id] = name
                    device_type = "sensor"

            if device_type:
                # update device registry
                dev_entry = dev_reg.async_get_device(identifiers={(DOMAIN, old_dev_id)})
                if dev_entry:
                    dev_reg.async_update_device(
                        dev_entry.id, new_identifiers={(DOMAIN, new_dev_id)}
                    )

                # update entity registry
                if device_type == "switch":
                    old_unique_id = f"rflink_switch_{old_dev_id}"
                    new_unique_id = f"rflink_switch_{new_dev_id}"
                    ent_entry = ent_reg.async_get_entity_id(
                        "switch", DOMAIN, old_unique_id
                    )
                    if ent_entry:
                        ent_reg.async_update_entity(
                            ent_entry, new_unique_id=new_unique_id
                        )
                elif device_type == "binary_sensor":
                    old_unique_id = f"rflink_binary_sensor_{old_dev_id}"
                    new_unique_id = f"rflink_binary_sensor_{new_dev_id}"
                    ent_entry = ent_reg.async_get_entity_id(
                        "binary_sensor", DOMAIN, old_unique_id
                    )
                    if ent_entry:
                        ent_reg.async_update_entity(
                            ent_entry, new_unique_id=new_unique_id
                        )
                else:
                    # For sensors, there are usually three: temperature, humidity and battery
                    for s_type in ["temperature", "humidity", "battery"]:
                        old_unique_id = f"rflink_sensor_{s_type}_{old_dev_id}"
                        new_unique_id = f"rflink_sensor_{s_type}_{new_dev_id}"
                        ent_entry = ent_reg.async_get_entity_id(
                            "sensor", DOMAIN, old_unique_id
                        )
                        if ent_entry:
                            ent_reg.async_update_entity(
                                ent_entry, new_unique_id=new_unique_id
                            )

            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="modify",
            data_schema=vol.Schema(
                {
                    vol.Required("device_id"): vol.In(all_devices),
                    vol.Required("new_device_id"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Remove a device."""
        configured_switches = self.options.get("switches", {})
        configured_sensors = self.options.get("sensors", {})
        configured_binary_sensors = self.options.get("binary_sensors", {})

        all_devices = {}
        for dev_id, name in configured_switches.items():
            all_devices[f"[Switch] {dev_id}"] = f"{name} ({dev_id})"
        for dev_id, config in configured_binary_sensors.items():
            name = config.get("name") if isinstance(config, dict) else config
            all_devices[f"[Binary Sensor] {dev_id}"] = f"{name} ({dev_id})"
        for dev_id, name in configured_sensors.items():
            all_devices[f"[Sensor] {dev_id}"] = f"{name} ({dev_id})"

        if not all_devices:
            return self.async_abort(reason="no_configured_devices")

        if user_input is not None:
            selection = user_input["device_id"]
            if selection.startswith("[Switch] "):
                dev_id = selection.replace("[Switch] ", "")
                self.options["switches"].pop(dev_id, None)
            elif selection.startswith("[Binary Sensor] "):
                dev_id = selection.replace("[Binary Sensor] ", "")
                self.options["binary_sensors"].pop(dev_id, None)
            elif selection.startswith("[Sensor] "):
                dev_id = selection.replace("[Sensor] ", "")
                self.options["sensors"].pop(dev_id, None)

            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="remove",
            data_schema=vol.Schema(
                {
                    vol.Required("device_id"): vol.In(all_devices),
                }
            ),
        )
