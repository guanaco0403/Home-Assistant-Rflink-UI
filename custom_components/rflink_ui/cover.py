"""Cover platform for RFLink UI."""

from typing import Any
import logging

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
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
    """Set up RFLink covers."""
    covers = entry.options.get("covers", {})
    async_add_entities(
        [
            RFLinkCover(entry.entry_id, device_id, config)
            for device_id, config in covers.items()
        ]
    )


class RFLinkCover(CoverEntity, RestoreEntity):
    """Representation of an RFLink cover."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_force_update = True
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(self, entry_id: str, device_id: str, config: Any) -> None:
        self._entry_id = entry_id
        self._device_id = device_id
        if isinstance(config, dict):
            self._device_name = config.get("name", device_id)
            self._inverted = bool(config.get("inverted", False))
        else:
            self._device_name = str(config)
            self._inverted = False

        self._attr_name = None
        self._attr_unique_id = f"rflink_cover_{device_id}"
        # RFLink/Somfy RTS does not report an absolute position.
        # Keep the position unknown instead of pretending UP=100% / DOWN=0%.
        self._attr_current_cover_position = None
        self._attr_is_opening = False
        self._attr_is_closing = False
        self._movement_state = "stopped"

        parts = device_id.split("_")
        if len(parts) >= 3:
            self._protocol = parts[0]
            self._rflink_id = parts[1]
            self._rflink_switch = "_".join(parts[2:])
        else:
            self._protocol = "Unknown"
            self._rflink_id = "0"
            self._rflink_switch = "0"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            manufacturer="RFLink",
            model=self._protocol,
        )

    @property
    def is_closed(self) -> bool | None:
        """Return None because RFLink does not report absolute position."""
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the useful RFLink movement state without inventing a position."""
        return {
            "movement_state": self._movement_state,
            "position_known": False,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        if (state := await self.async_get_last_state()) is not None:
            # Do not restore a fake position. Restore only the movement state.
            self._attr_current_cover_position = None
            self._attr_is_opening = state.state == "opening"
            self._attr_is_closing = state.state == "closing"
            self._movement_state = (
                "opening"
                if self._attr_is_opening
                else "closing" if self._attr_is_closing else "stopped"
            )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"rflink_update_{self._device_id}",
                self._handle_rflink_update,
            )
        )

    @callback
    def _handle_rflink_update(self, data_dict: dict[str, str]) -> None:
        cmd = data_dict.get("CMD", "").upper()
        if cmd == "UP":
            self._set_direction(opening=not self._inverted)
        elif cmd == "DOWN":
            self._set_direction(opening=self._inverted)
        elif cmd == "STOP":
            self._attr_is_opening = False
            self._attr_is_closing = False
            self._movement_state = "stopped"
        else:
            return
        self.async_write_ha_state()

    def _set_direction(self, opening: bool) -> None:
        """Set movement state without fabricating an absolute position."""
        self._attr_is_opening = opening
        self._attr_is_closing = not opening
        self._movement_state = "opening" if opening else "closing"
        self._attr_current_cover_position = None

    async def _send(self, command: str) -> None:
        data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        if not data:
            return
        frame = (
            f"10;{self._protocol};{self._rflink_id};{self._rflink_switch};{command};\n"
        )
        try:
            await data.async_send_command(frame)
        except Exception:
            _LOGGER.exception("Failed to send RFLink cover command %s", command)

    async def async_open_cover(self, **kwargs: Any) -> None:
        command = "DOWN" if self._inverted else "UP"
        await self._send(command)
        self._set_direction(opening=True)
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        command = "UP" if self._inverted else "DOWN"
        await self._send(command)
        self._set_direction(opening=False)
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._send("STOP")
        self._attr_is_opening = False
        self._attr_is_closing = False
        self._movement_state = "stopped"
        self.async_write_ha_state()
