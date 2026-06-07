import asyncio
import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rflink_ui import DOMAIN


async def test_switch_setup_and_control(hass, mock_serial_connection):
    """Test setting up a switch, receiving updates, and controlling it."""
    # Define a switch in options
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={
            "switches": {"Unitec_1a4a_4": "Living Room Switch"},
            "sensors": {},
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await asyncio.sleep(0.01)

    # 1. Verify entity creation
    state = hass.states.get("switch.living_room_switch")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes.get("friendly_name") == "Living Room Switch"

    # 2. Simulate dispatcher update (Turn ON)
    # Dispatcher updates the state by sending the raw parsed dictionary
    from homeassistant.helpers.dispatcher import dispatcher_send
    dispatcher_send(
        hass,
        "rflink_update_Unitec_1a4a_4",
        {"CMD": "ON"}
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.living_room_switch")
    assert state.state == STATE_ON

    # Simulate dispatcher update (Turn OFF)
    dispatcher_send(
        hass,
        "rflink_update_Unitec_1a4a_4",
        {"CMD": "OFF"}
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.living_room_switch")
    assert state.state == STATE_OFF

    # 3. Control via service calls (Turn ON)
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.living_room_switch"},
        blocking=True,
    )
    
    state = hass.states.get("switch.living_room_switch")
    assert state.state == STATE_ON

    # Check if the command was written to serial connection
    # Expected command: 10;Unitec;1a4a;4;ON;\n
    writer = mock_serial_connection["writer"]
    assert b"10;Unitec;1a4a;4;ON;\n" in writer.written

    # Control via service calls (Turn OFF)
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.living_room_switch"},
        blocking=True,
    )
    
    state = hass.states.get("switch.living_room_switch")
    assert state.state == STATE_OFF
    assert b"10;Unitec;1a4a;4;OFF;\n" in writer.written
