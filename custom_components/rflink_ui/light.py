"""Light platform for RFLink UI."""

from typing import Any
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the RFLink light platform."""
    lights = entry.options.get("lights", {})

    entities = []
    for device_id, config in lights.items():
        name = config.get("name") if isinstance(config, dict) else config
        light_type = (
            config.get("type", "dimmable") if isinstance(config, dict) else "dimmable"
        )
        entities.append(RFLinkLight(entry.entry_id, device_id, name, light_type))

    async_add_entities(entities)


class RFLinkLight(LightEntity, RestoreEntity):
    """Representation of an RFLink light dimmer."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, entry_id: str, device_id: str, name: str, light_type: str
    ) -> None:
        """Initialize the light."""
        self._entry_id = entry_id
        self._device_id = device_id
        self._device_name = name
        self._light_type = light_type
        self._attr_name = None
        self._attr_unique_id = f"rflink_light_{device_id}"
        self._attr_is_on = False

        if self._light_type in ["dimmable", "hybrid"]:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_brightness = 255
        else:
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_brightness = None

        # device_id is expected to be protocol_id_switch, e.g., Unitec_1a4a_4
        parts = device_id.split("_")
        if len(parts) >= 3:
            self._protocol = parts[0]
            self._rflink_id = parts[1]
            self._rflink_switch = parts[2]
        else:
            self._protocol = "Unknown"
            self._rflink_id = "0"
            self._rflink_switch = "0"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this RFLink device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            manufacturer="RFLink",
            model=self._protocol,
        )

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return self._attr_brightness

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        if (state := await self.async_get_last_state()) is not None:
            self._attr_is_on = state.state == STATE_ON
            if (
                self._light_type in ["dimmable", "hybrid"]
                and ATTR_BRIGHTNESS in state.attributes
            ):
                self._attr_brightness = int(state.attributes[ATTR_BRIGHTNESS])

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"rflink_update_{self._device_id}",
                self._handle_rflink_update,
            )
        )

    @callback
    def _handle_rflink_update(self, data_dict: dict[str, str]) -> None:
        """Handle updated data from RFLink."""
        cmd = data_dict.get("CMD", "")
        _LOGGER.debug("Light %s received update: %s", self._device_id, cmd)

        if self._light_type == "toggle":
            if cmd.upper() == "ON":
                self._attr_is_on = self._attr_is_on in [None, False]
            self.async_write_ha_state()
            return

        if cmd.startswith("SET_LEVEL="):
            try:
                level = int(cmd.split("=")[1])
                if self._light_type in ["dimmable", "hybrid"]:
                    self._attr_brightness = min(255, level * 17)
                self._attr_is_on = True
            except (ValueError, IndexError):
                pass
        elif cmd.isdigit():
            level = int(cmd)
            if self._light_type in ["dimmable", "hybrid"]:
                self._attr_brightness = min(255, level * 17)
            self._attr_is_on = True
        elif cmd.upper() in ["ON", "ALLON"]:
            self._attr_is_on = True
        elif cmd.upper() in ["OFF", "ALLOFF"]:
            self._attr_is_on = False

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        if not data:
            return

        if self._light_type == "toggle":
            command = (
                f"10;{self._protocol};{self._rflink_id};{self._rflink_switch};ON;\n"
            )
            await data.async_send_command(command)
            self._attr_is_on = self._attr_is_on in [None, False]
            self.async_write_ha_state()
            return

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None and self._light_type in ["dimmable", "hybrid"]:
            # Map 0-255 brightness to 0-15 level
            level = int(brightness / 17)
            self._attr_brightness = level * 17

            # Command format: 10;Protocol;ID;Switch;LEVEL;\n
            command = f"10;{self._protocol};{self._rflink_id};{self._rflink_switch};{level};\n"
            await data.async_send_command(command)

        if (
            brightness is None
            or self._light_type == "hybrid"
            or self._light_type == "switchable"
        ):
            # For hybrid, switchable, or if no brightness was requested, send ON command
            command = (
                f"10;{self._protocol};{self._rflink_id};{self._rflink_switch};ON;\n"
            )
            await data.async_send_command(command)

        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        if not data:
            return

        if self._light_type == "toggle":
            command = (
                f"10;{self._protocol};{self._rflink_id};{self._rflink_switch};ON;\n"
            )
            await data.async_send_command(command)
            self._attr_is_on = self._attr_is_on in [None, False]
            self.async_write_ha_state()
            return

        command = f"10;{self._protocol};{self._rflink_id};{self._rflink_switch};OFF;\n"

        try:
            await data.async_send_command(command)
            self._attr_is_on = False
            self.async_write_ha_state()
        except Exception:
            pass
