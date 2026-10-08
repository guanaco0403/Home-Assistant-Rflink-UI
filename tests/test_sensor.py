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


async def test_f007_th_channel_alias(hass, mock_serial_connection):
    """Test F007_TH sensor setup using stable channel ID (F007_TH_CH7)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={
            "switches": {},
            "sensors": {"F007_TH_CH7": "Patio Sensor"},
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Simulate receiving RFLink packet with raw ID 45246 (lowest hex digit 6 -> CH7)
    from custom_components.rflink_ui import _process_packet
    _process_packet(hass, entry.entry_id, "20;62;F007_TH;ID=45246;TEMP=00d2;HUM=55;BAT=OK;")
    await hass.async_block_till_done()

    temp_state = hass.states.get("sensor.patio_sensor_temperature")
    assert temp_state is not None
    assert temp_state.state == "21.0"

    hum_state = hass.states.get("sensor.patio_sensor_humidity")
    assert hum_state is not None
    assert hum_state.state == "55"

    battery_state = hass.states.get("sensor.patio_sensor_battery")
    assert battery_state is not None
    assert battery_state.state == "OK"


async def test_rain_sensor_updates(hass, mock_serial_connection):
    """Test rain sensor entity creation and RAIN packet parsing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={
            "switches": {},
            "sensors": {"Auriol Rain_0057": "Rain Gauge"},
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    rain_state = hass.states.get("sensor.rain_gauge_total_rain")
    assert rain_state is not None
    assert rain_state.state == "unknown"
    assert rain_state.attributes.get("unit_of_measurement") == "mm"

    # Simulate RFLink packet: RAIN=0064 -> hex 64 = 100 -> 10.0 mm
    from custom_components.rflink_ui import _process_packet
    _process_packet(hass, entry.entry_id, "20;3B;Auriol Rain;ID=0057;RAIN=0064;BAT=OK;")
    await hass.async_block_till_done()

    rain_state = hass.states.get("sensor.rain_gauge_total_rain")
    assert rain_state is not None
    assert rain_state.state == "10.0"
    assert rain_state.attributes.get("battery") == "OK"


async def test_sensor_force_update_same_value(hass, mock_serial_connection):
    """Test that last_updated changes even if sensor value is unchanged."""
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

    from homeassistant.helpers.dispatcher import dispatcher_send

    dispatcher_send(
        hass,
        "rflink_update_Oregon_0A4C",
        {"TEMP": "00ba", "BAT": "OK"},
    )
    await hass.async_block_till_done()

    state1 = hass.states.get("sensor.garden_sensor_temperature")
    assert state1.state == "18.6"
    last_updated1 = state1.last_updated

    await asyncio.sleep(0.01)

    # Dispatch same value again
    dispatcher_send(
        hass,
        "rflink_update_Oregon_0A4C",
        {"TEMP": "00ba", "BAT": "OK"},
    )
    await hass.async_block_till_done()

    state2 = hass.states.get("sensor.garden_sensor_temperature")
    assert state2.state == "18.6"
    assert state2.last_updated > last_updated1



