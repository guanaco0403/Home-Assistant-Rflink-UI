import asyncio
import datetime
from unittest.mock import MagicMock
from collections import deque

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.rflink_ui import DOMAIN


async def test_binary_sensor_setup_and_updates(hass, mock_serial_connection):
    """Test setting up binary sensors and receiving command updates."""
    # Define binary sensors in options
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={
            "switches": {},
            "sensors": {},
            "binary_sensors": {
                "Kaku_1234_1": "Motion Sensor",
                "NewKaku_abc_2": {
                    "name": "Door Sensor",
                    "device_class": "opening",
                    "off_delay": 5,
                }
            },
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await asyncio.sleep(0.01)

    # 1. Verify entities were created
    motion_state = hass.states.get("binary_sensor.motion_sensor")
    assert motion_state is not None
    assert motion_state.state == STATE_OFF
    # Auto-detected device class based on name "Motion Sensor"
    assert motion_state.attributes.get("device_class") == "motion"

    door_state = hass.states.get("binary_sensor.door_sensor")
    assert door_state is not None
    assert door_state.state == STATE_OFF
    assert door_state.attributes.get("device_class") == "opening"

    # 2. Test update with "ON" for Motion Sensor
    dispatcher_send(
        hass,
        "rflink_update_Kaku_1234_1",
        {"CMD": "ON"}
    )
    await hass.async_block_till_done()

    motion_state = hass.states.get("binary_sensor.motion_sensor")
    assert motion_state.state == STATE_ON

    # 3. Test update with "OFF" for Motion Sensor
    dispatcher_send(
        hass,
        "rflink_update_Kaku_1234_1",
        {"CMD": "OFF"}
    )
    await hass.async_block_till_done()

    motion_state = hass.states.get("binary_sensor.motion_sensor")
    assert motion_state.state == STATE_OFF

    # 4. Test other universal commands (OPEN / CLOSE)
    dispatcher_send(
        hass,
        "rflink_update_NewKaku_abc_2",
        {"CMD": "OPEN"}
    )
    await hass.async_block_till_done()

    door_state = hass.states.get("binary_sensor.door_sensor")
    assert door_state.state == STATE_ON

    dispatcher_send(
        hass,
        "rflink_update_NewKaku_abc_2",
        {"CMD": "CLOSE"}
    )
    await hass.async_block_till_done()

    door_state = hass.states.get("binary_sensor.door_sensor")
    assert door_state.state == STATE_OFF

    # Clean up entry
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_binary_sensor_off_delay(hass, mock_serial_connection):
    """Test that a binary sensor with off_delay turns off automatically."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={
            "switches": {},
            "sensors": {},
            "binary_sensors": {
                "Kaku_motion": {
                    "name": "PIR Sensor",
                    "device_class": "motion",
                    "off_delay": 2,
                }
            },
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.pir_sensor")
    assert state.state == STATE_OFF

    # Trigger motion
    dispatcher_send(
        hass,
        "rflink_update_Kaku_motion",
        {"CMD": "MOTION"}
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.pir_sensor")
    assert state.state == STATE_ON

    # Get current time
    now = dt_util.utcnow()

    # Tick time forward by 1 second (should still be ON)
    async_fire_time_changed(hass, now + datetime.timedelta(seconds=1))
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.pir_sensor")
    assert state.state == STATE_ON

    # Tick time forward by another 1.5 seconds (total 2.5s, should turn OFF)
    async_fire_time_changed(hass, now + datetime.timedelta(seconds=2.5))
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.pir_sensor")
    assert state.state == STATE_OFF

    # Clean up entry
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_options_flow_binary_sensors(hass, mock_serial_connection):
    """Test options flow configuration paths for binary sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={"switches": {}, "sensors": {}, "binary_sensors": {}},
    )
    entry.add_to_hass(hass)

    # 1. Add binary sensor manually
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_manual"},
    )
    assert result["step_id"] == "add_manual"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "device_type": "Binary Sensor",
            "device_id": "Kaku_manual_bin",
            "name": "Manual Bin Sensor",
        },
    )
    # Should show the options form
    assert result["step_id"] == "binary_sensor_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "device_class": "opening",
            "off_delay": 10,
        },
    )
    assert result["type"] == "create_entry"
    assert entry.options["binary_sensors"]["Kaku_manual_bin"] == {
        "name": "Manual Bin Sensor",
        "device_class": "opening",
        "off_delay": 10,
    }

    # 2. Add binary sensor learned
    mock_data = MagicMock()
    # CMD indicates switch type -> can be switch or binary sensor
    mock_data.recent_unknown_devices = deque([
        ("Kaku_learned_bin", {"type": "switch", "data": {"CMD": "ON"}}),
    ])
    hass.data[DOMAIN] = {entry.entry_id: mock_data}

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_learned"},
    )
    assert result["step_id"] == "add_learned"

    # Select learned binary sensor
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "device_id": "[Binary Sensor] Kaku_learned_bin",
            "name": "Learned Bin Sensor",
        },
    )
    assert result["step_id"] == "binary_sensor_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "device_class": "motion",
            "off_delay": 5,
        },
    )
    assert result["type"] == "create_entry"
    assert entry.options["binary_sensors"]["Kaku_learned_bin"] == {
        "name": "Learned Bin Sensor",
        "device_class": "motion",
        "off_delay": 5,
    }

    # 3. Modify binary sensor
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "modify"},
    )
    assert result["step_id"] == "modify"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "device_id": "[Binary Sensor] Kaku_learned_bin",
            "new_device_id": "Kaku_modified_bin",
        },
    )
    assert result["type"] == "create_entry"
    assert "Kaku_learned_bin" not in entry.options["binary_sensors"]
    assert entry.options["binary_sensors"]["Kaku_modified_bin"]["name"] == "Learned Bin Sensor"

    # 4. Remove binary sensor
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "remove"},
    )
    assert result["step_id"] == "remove"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "device_id": "[Binary Sensor] Kaku_modified_bin",
        },
    )
    assert result["type"] == "create_entry"
    assert "Kaku_modified_bin" not in entry.options["binary_sensors"]
