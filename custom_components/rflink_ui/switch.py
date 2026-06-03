"""Switch platform for RFLink UI."""

from typing import Any
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the RFLink switch platform."""
    switches = entry.options.get("switches", {})

    entities = []
    for device_id, name in switches.items():
        entities.append(RFLinkSwitch(entry.entry_id, device_id, name))

    async_add_entities(entities)


class RFLinkSwitch(SwitchEntity):
    """Representation of an RFLink switch."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry_id: str, device_id: str, name: str) -> None:
        """Initialize the switch."""
        self._entry_id = entry_id
        self._device_id = device_id
        self._attr_name = name
        self._attr_unique_id = f"rflink_switch_{device_id}"
        self._attr_is_on = False

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
            name=self._attr_name,
            manufacturer="RFLink",
            model=self._protocol,
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
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
        _LOGGER.debug("Switch %s received update: %s", self._device_id, cmd)

        if cmd.upper() in ["ON", "ALLON"]:
            self._attr_is_on = True
        elif cmd.upper() in ["OFF", "ALLOFF"]:
            self._attr_is_on = False

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        if not data:
            return

        # Standard syntax: 10;Protocol;ID;Switch;ON;\n
        command = f"10;{self._protocol};{self._rflink_id};{self._rflink_switch};ON;\n"

        try:
            await data.async_send_command(command)
            self._attr_is_on = True
            self.async_write_ha_state()
        except Exception:
            pass

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        if not data:
            return

        command = f"10;{self._protocol};{self._rflink_id};{self._rflink_switch};OFF;\n"

        try:
            await data.async_send_command(command)
            self._attr_is_on = False
            self.async_write_ha_state()
        except Exception:
            pass
