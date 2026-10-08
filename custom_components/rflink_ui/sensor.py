"""Sensor platform for RFLink UI."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
    RestoreSensor,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfTemperature,
    UnitOfPrecipitationDepth,
    PERCENTAGE,
)
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
    """Set up the RFLink sensor platform."""
    sensors = entry.options.get("sensors", {})

    entities = []
    for device_id, name in sensors.items():
        entities.append(RFLinkSensor(entry.entry_id, device_id, name, "temperature"))
        entities.append(RFLinkSensor(entry.entry_id, device_id, name, "humidity"))
        entities.append(RFLinkSensor(entry.entry_id, device_id, name, "battery"))
        entities.append(RFLinkSensor(entry.entry_id, device_id, name, "total_rain"))

    if entities:
        async_add_entities(entities)


class RFLinkSensor(RestoreSensor):
    """Representation of an RFLink sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_force_update = True

    def __init__(
        self, entry_id: str, device_id: str, name: str, sensor_type: str
    ) -> None:
        """Initialize the sensor."""
        self._device_id = device_id
        self._original_name = name
        self._sensor_type = sensor_type

        # Name of the entity, e.g. "Temperature" or "Humidity"
        if sensor_type == "temperature":
            self._attr_name = "Temperature"
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        elif sensor_type == "humidity":
            self._attr_name = "Humidity"
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = PERCENTAGE
        elif sensor_type == "battery":
            self._attr_name = "Battery"
            self._attr_icon = "mdi:battery"
        elif sensor_type in ["total_rain", "rain"]:
            self._attr_name = "Total Rain"
            self._attr_device_class = SensorDeviceClass.PRECIPITATION
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            self._attr_native_unit_of_measurement = UnitOfPrecipitationDepth.MILLIMETERS
        else:
            self._attr_name = sensor_type.capitalize()

        self._attr_unique_id = f"rflink_sensor_{sensor_type}_{device_id}"
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

        # device_id could be F007_TH_45291. Splitting by "_" gives parts.
        parts = device_id.rsplit("_", 1)
        if len(parts) >= 2:
            self._protocol = parts[0]
            self._rflink_id = parts[1]
        else:
            self._protocol = "Unknown"
            self._rflink_id = "0"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this RFLink device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._original_name,
            manufacturer="RFLink",
            model=self._protocol,
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        last_sensor_data = await self.async_get_last_sensor_data()
        if last_sensor_data is not None:
            self._attr_native_value = last_sensor_data.native_value

        last_state = await self.async_get_last_state()
        if last_state is not None:
            # Restore attributes like battery, etc.
            self._attr_extra_state_attributes = dict(last_state.attributes)

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
        _LOGGER.debug(
            "Sensor %s (%s) received update: %s",
            self._device_id,
            self._sensor_type,
            data_dict,
        )

        attributes = dict(self._attr_extra_state_attributes)
        has_update = False

        if self._sensor_type == "temperature":
            if "TEMP" in data_dict:
                try:
                    temp_hex = data_dict["TEMP"]
                    temp_int = int(temp_hex, 16)
                    if temp_int & 0x8000:
                        temp_val = -(temp_int & 0x7FFF) / 10.0
                    else:
                        temp_val = temp_int / 10.0
                    self._attr_native_value = temp_val
                    has_update = True
                except ValueError:
                    attributes["temperature_raw"] = data_dict["TEMP"]

        elif self._sensor_type == "humidity":
            if "HUM" in data_dict:
                try:
                    hum_int = int(data_dict["HUM"])
                    self._attr_native_value = hum_int
                    has_update = True
                except ValueError:
                    attributes["humidity_raw"] = data_dict["HUM"]

        elif self._sensor_type == "battery":
            if "BAT" in data_dict:
                self._attr_native_value = data_dict["BAT"]
                has_update = True

        elif self._sensor_type in ["total_rain", "rain"]:
            if "RAIN" in data_dict:
                try:
                    rain_hex = data_dict["RAIN"]
                    rain_int = int(rain_hex, 16)
                    self._attr_native_value = rain_int / 10.0
                    has_update = True
                except ValueError:
                    try:
                        self._attr_native_value = float(data_dict["RAIN"]) / 10.0
                        has_update = True
                    except ValueError:
                        attributes["rain_raw"] = data_dict["RAIN"]

        if "BAT" in data_dict:
            attributes["battery"] = data_dict["BAT"]
            has_update = True

        # Store any other unknown values
        for key, value in data_dict.items():
            if key not in ["ID", "TEMP", "HUM", "BAT", "RAIN"]:
                attributes[key.lower()] = value
                has_update = True

        self._attr_extra_state_attributes = attributes

        if has_update or self._attr_native_value is not None:
            self.async_write_ha_state()
