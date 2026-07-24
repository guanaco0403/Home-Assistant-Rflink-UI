"""Cover platform for RFLink UI."""

from typing import Any
import logging

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Some protocols (eg. KlikAanKlikUit / "newkaku") have UP/DOWN reversed.
# CMD values received from - or sent to - RFLink that mean "open"/"close".
OPEN_COMMANDS = {"ON", "ALLON", "UP"}
CLOSE_COMMANDS = {"OFF", "ALLOFF", "DOWN"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the RFLink cover platform."""
    covers = entry.options.get("covers", {})

    entities = []
    for device_id, config in covers.items():
        entities.append(RFLinkCover(entry.entry_id, device_id, config))

    async_add_entities(entities)


class RFLinkCover(CoverEntity, RestoreEntity):
    """Representation of an RFLink cover (eg. roller shutter/blind)."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_assumed_state = True
    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(self, entry_id: str, device_id: str, config: dict | str) -> None:
        """Initialize the cover."""
        self._entry_id = entry_id
        self._device_id = device_id

        if isinstance(config, dict):
            self._device_name = config.get("name")
            self._inverted = bool(config.get("inverted", False))
        else:
            # Backwards compatible: plain name string, no inversion.
            self._device_name = config
            self._inverted = False

        self._attr_name = None
        self._attr_unique_id = f"rflink_cover_{device_id}"
        # Assume closed until we learn otherwise (from restored/received state).
        self._is_open = False

        # device_id is expected to be protocol_id_switch, e.g., Somfy_1a4a_1
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
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        return not self._is_open

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        if (state := await self.async_get_last_state()) is not None:
            self._is_open = state.state == "open"

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"rflink_update_{self._device_id}",
                self._handle_rflink_update,
            )
        )

    @callback
    def _handle_rflink_update(self, data_dict: dict[str, str]) -> None:
        """Handle updated data from RFLink (eg. a physical remote was used)."""
        cmd = data_dict.get("CMD", "").upper()
        _LOGGER.debug("Cover %s received update: %s", self._device_id, cmd)

        # STOP does not tell us a definitive open/closed state, ignore it.
        if cmd in OPEN_COMMANDS:
            self._is_open = not self._inverted
        elif cmd in CLOSE_COMMANDS:
            self._is_open = self._inverted
        else:
            return

        self.async_write_ha_state()

    def _command_for(self, base_command: str) -> str:
        """Map a logical UP/DOWN command onto the wire command, honouring inversion."""
        if not self._inverted:
            return base_command
        return {"UP": "DOWN", "DOWN": "UP"}.get(base_command, base_command)

    async def _async_send(self, command: str) -> None:
        """Send a raw RFLink command for this device."""
        data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        if not data:
            return

        # Standard syntax: 10;Protocol;ID;Switch;COMMAND;\n
        line = f"10;{self._protocol};{self._rflink_id};{self._rflink_switch};{command};\n"

        try:
            await data.async_send_command(line)
        except Exception:
            pass

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._async_send(self._command_for("UP"))
        self._is_open = True
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._async_send(self._command_for("DOWN"))
        self._is_open = False
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover.

        Not every RFLink-supported protocol implements STOP; RFLink will
        simply ignore the command for those that don't.
        """
        await self._async_send("STOP")
