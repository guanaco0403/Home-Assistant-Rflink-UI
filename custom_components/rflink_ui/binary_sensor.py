"""Binary sensor platform for RFLink UI."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.event import async_call_later

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

    binary_sensors = entry.options.get("binary_sensors", {})
    for device_id, name in binary_sensors.items():
        entities.append(RFLinkBinarySensor(entry.entry_id, device_id, name))

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


class RFLinkBinarySensor(BinarySensorEntity, RestoreEntity):
    """Representation of an RFLink binary sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry_id: str, device_id: str, config: dict | str) -> None:
        """Initialize the binary sensor."""
        self._entry_id = entry_id
        self._device_id = device_id
        self._delay_listener = None

        if isinstance(config, dict):
            self._device_name = config.get("name")
            self._off_delay = config.get("off_delay")
            device_class = config.get("device_class")
            self._attr_device_class = (
                BinarySensorDeviceClass(device_class)
                if device_class and device_class != "none"
                else None
            )
        else:
            self._device_name = config
            self._off_delay = None
            self._attr_device_class = self._detect_device_class(device_id, config)

        self._attr_name = None
        self._attr_unique_id = f"rflink_binary_sensor_{device_id}"
        self._attr_is_on = False

        # device_id is expected to be protocol_id_switch, e.g., Unitec_1a4a_4
        parts = device_id.split("_")
        if len(parts) >= 2:
            self._protocol = parts[0]
            self._rflink_id = parts[1]
        else:
            self._protocol = "Unknown"
            self._rflink_id = "0"

    def _detect_device_class(
        self, device_id: str, name: str
    ) -> BinarySensorDeviceClass | None:
        """Attempt to detect device class from device_id or name."""
        name_lower = name.lower()
        id_lower = device_id.lower()
        if (
            "motion" in name_lower
            or "pir" in name_lower
            or "detect" in name_lower
            or "motion" in id_lower
        ):
            return BinarySensorDeviceClass.MOTION
        if (
            "door" in name_lower
            or "window" in name_lower
            or "opening" in name_lower
            or "door" in id_lower
            or "window" in id_lower
        ):
            return BinarySensorDeviceClass.OPENING
        if (
            "smoke" in name_lower
            or "co" in name_lower
            or "gas" in name_lower
            or "smoke" in id_lower
        ):
            return BinarySensorDeviceClass.SMOKE
        if (
            "moisture" in name_lower
            or "water" in name_lower
            or "flood" in name_lower
            or "leak" in name_lower
        ):
            return BinarySensorDeviceClass.MOISTURE
        if "connectivity" in name_lower or "ping" in name_lower:
            return BinarySensorDeviceClass.CONNECTIVITY
        return None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this RFLink device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            manufacturer="RFLink",
            model=self._protocol,
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        if (state := await self.async_get_last_state()) is not None:
            self._attr_is_on = state.state == STATE_ON

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"rflink_update_{self._device_id}",
                self._handle_rflink_update,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity is about to be removed."""
        if self._delay_listener:
            self._delay_listener()
            self._delay_listener = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_rflink_update(self, data_dict: dict[str, str]) -> None:
        """Handle updated data from RFLink."""
        cmd = data_dict.get("CMD", "")
        _LOGGER.debug("Binary sensor %s received update: %s", self._device_id, cmd)

        # Set state based on CMD
        if cmd.upper() in ["ON", "ALLON", "OPEN", "MOTION"]:
            self._attr_is_on = True
        elif cmd.upper() in ["OFF", "ALLOFF", "CLOSE", "OK"]:
            self._attr_is_on = False
        else:
            return

        # Handle off_delay if configured
        if self._off_delay:
            if self._delay_listener:
                self._delay_listener()
                self._delay_listener = None

            @callback
            def _off_delay_listener(now):
                """Switch device back to off."""
                self._delay_listener = None
                self._attr_is_on = False
                self.async_write_ha_state()

            self._delay_listener = async_call_later(
                self.hass, self._off_delay, _off_delay_listener
            )

        self.async_write_ha_state()
