"""Binary sensor platform for RFLink UI connection status."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """Set up the RFLink binary sensor platform."""
    entities = [
        RFLinkConnectionSensor(entry.entry_id, entry.data.get("port", "RFLink"))
    ]
    async_add_entities(entities)


class RFLinkConnectionSensor(BinarySensorEntity):
    """Representation of an RFLink connection status sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, entry_id: str, port: str) -> None:
        """Initialize the connection sensor."""
        self._entry_id = entry_id
        self._attr_name = "Connection status"
        self._attr_unique_id = f"rflink_connection_{port}"
        self._attr_is_on = False
        self._port = port

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=f"RFLink ({self._port})",
            manufacturer="RFLink",
            model="Gateway",
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        # Get current state from memory
        data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        if data:
            self._attr_is_on = data.is_connected

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"rflink_connection_{self._entry_id}",
                self._handle_connection_update,
            )
        )

    @callback
    def _handle_connection_update(self, is_connected: bool) -> None:
        """Handle updated connection status."""
        self._attr_is_on = is_connected
        self.async_write_ha_state()
