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
                await self.hass.async_add_executor_job(
                    self._test_serial_port, port
                )
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=f"RFLink ({port})", data=user_input)

        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        port_list = [port.device for port in ports]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PORT, default=port_list[0] if port_list else ""): vol.In(port_list) if port_list else str,
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

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_learned", "add_manual", "remove"],
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
                    if selection.startswith("[Interrupteur] "):
                        dev_id = selection.replace("[Interrupteur] ", "")
                        self.options["switches"][dev_id] = name
                    elif selection.startswith("[Capteur] "):
                        dev_id = selection.replace("[Capteur] ", "")
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
            for dev_id, info in data.recent_unknown_devices:
                if dev_id not in configured_switches and dev_id not in configured_sensors:
                    has_devices = True
                    if info["type"] == "switch":
                        key = f"[Interrupteur] {dev_id}"
                        devices_dict[key] = f"{key}"
                    else:
                        key = f"[Capteur] {dev_id}"
                        devices_dict[key] = f"{key}"

        if not has_devices:
            errors["base"] = "no_devices_found"

        return self.async_show_form(
            step_id="add_learned",
            data_schema=vol.Schema({
                vol.Required("device_id", default="refresh"): vol.In(devices_dict),
                vol.Optional("name"): str,
            }),
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
            
            if dev_type == "Switch" or dev_type == "Interrupteur":
                self.options["switches"][dev_id] = name
            else:
                self.options["sensors"][dev_id] = name
                
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="add_manual",
            data_schema=vol.Schema({
                vol.Required("device_type", default="Switch"): vol.In(["Switch", "Sensor"]),
                vol.Required("device_id"): str,
                vol.Required("name"): str,
            })
        )

    async def async_step_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Remove a device."""
        configured_switches = self.options.get("switches", {})
        configured_sensors = self.options.get("sensors", {})
        
        all_devices = []
        for dev_id in configured_switches:
            all_devices.append(f"[Interrupteur] {dev_id}")
        for dev_id in configured_sensors:
            all_devices.append(f"[Capteur] {dev_id}")

        if not all_devices:
            return self.async_abort(reason="no_configured_devices")

        if user_input is not None:
            selection = user_input["device_id"]
            if selection.startswith("[Interrupteur] "):
                dev_id = selection.replace("[Interrupteur] ", "")
                self.options["switches"].pop(dev_id, None)
            elif selection.startswith("[Capteur] "):
                dev_id = selection.replace("[Capteur] ", "")
                self.options["sensors"].pop(dev_id, None)
                
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="remove",
            data_schema=vol.Schema({
                vol.Required("device_id"): vol.In(all_devices),
            })
        )
