import asyncio

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rflink_ui import DOMAIN


async def test_sensor_setup_and_updates(hass, mock_serial_connection):
    """Test setting up a sensor and receiving temperature and humidity updates."""
    # Define a sensor in options
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={
            "switches": {},
            "sensors": {"Oregon_0A4C": "Garden Sensor"},
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await asyncio.sleep(0.01)

    # 1. Verify entity creation (Temperature, Humidity, and Battery entities should be created)
    temp_state = hass.states.get("sensor.garden_sensor_temperature")
    assert temp_state is not None
    assert temp_state.state == "unknown"
    assert temp_state.attributes.get("unit_of_measurement") == "°C"

    hum_state = hass.states.get("sensor.garden_sensor_humidity")
    assert hum_state is not None
    assert hum_state.state == "unknown"
    assert hum_state.attributes.get("unit_of_measurement") == "%"

    battery_state = hass.states.get("sensor.garden_sensor_battery")
    assert battery_state is not None
    assert battery_state.state == "unknown"
    assert battery_state.attributes.get("icon") == "mdi:battery"

    # 2. Simulate dispatcher update (Positive temperature + humidity + OK battery)
    # TEMP = "00ba" hex = 186 dec -> 18.6°C
    # HUM = "40" -> 40%
    # BAT = "OK"
    # RSSI = "6" (custom/unknown key)
    from homeassistant.helpers.dispatcher import dispatcher_send
    dispatcher_send(
        hass,
        "rflink_update_Oregon_0A4C",
        {
            "TEMP": "00ba",
            "HUM": "40",
            "BAT": "OK",
            "RSSI": "6"
        }
    )
    await hass.async_block_till_done()

    # Verify state updates
    temp_state = hass.states.get("sensor.garden_sensor_temperature")
    assert temp_state.state == "18.6"
    assert temp_state.attributes.get("battery") == "OK"
    assert temp_state.attributes.get("rssi") == "6"

    hum_state = hass.states.get("sensor.garden_sensor_humidity")
    assert hum_state.state == "40"
    assert hum_state.attributes.get("battery") == "OK"

    battery_state = hass.states.get("sensor.garden_sensor_battery")
    assert battery_state.state == "OK"

    # 3. Simulate dispatcher update (Negative temperature + LOW battery)
    # -5.4°C = 54 dec. High bit 0x8000 set -> 0x8036 hex = "8036"
    dispatcher_send(
        hass,
        "rflink_update_Oregon_0A4C",
        {
            "TEMP": "8036",
            "BAT": "LOW",
        }
    )
    await hass.async_block_till_done()

    temp_state = hass.states.get("sensor.garden_sensor_temperature")
    assert temp_state.state == "-5.4"
    assert temp_state.attributes.get("battery") == "LOW"

    battery_state = hass.states.get("sensor.garden_sensor_battery")
    assert battery_state.state == "LOW"
