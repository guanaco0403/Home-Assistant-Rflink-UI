"""Tests for the RFLink cover platform."""

import asyncio
from unittest.mock import patch

from homeassistant.core import State
from homeassistant.helpers.dispatcher import dispatcher_send
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rflink_ui import DOMAIN


async def test_cover_setup_and_control(hass, mock_serial_connection):
    """Test standard cover setup, service calls, and dispatcher updates."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={
            "covers": {
                "RTS_0a1b2c_0": {
                    "name": "Living Room Blinds",
                    "inverted": False,
                }
            },
            "switches": {},
            "sensors": {},
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await asyncio.sleep(0.01)

    # 1. Verify entity creation
    state = hass.states.get("cover.living_room_blinds")
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes.get("friendly_name") == "Living Room Blinds"
    assert state.attributes.get("movement_state") == "stopped"
    assert state.attributes.get("position_known") is False
    assert state.attributes.get("current_position") is None

    # 2. Open cover service call
    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.living_room_blinds"},
        blocking=True,
    )
    state = hass.states.get("cover.living_room_blinds")
    assert state.state == "opening"
    assert state.attributes.get("movement_state") == "opening"
    writer = mock_serial_connection["writer"]
    assert b"10;RTS;0a1b2c;0;UP;\n" in writer.written

    # 3. Stop cover service call
    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": "cover.living_room_blinds"},
        blocking=True,
    )
    state = hass.states.get("cover.living_room_blinds")
    assert state.state == "unknown"
    assert state.attributes.get("movement_state") == "stopped"
    assert b"10;RTS;0a1b2c;0;STOP;\n" in writer.written

    # 4. Close cover service call
    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": "cover.living_room_blinds"},
        blocking=True,
    )
    state = hass.states.get("cover.living_room_blinds")
    assert state.state == "closing"
    assert state.attributes.get("movement_state") == "closing"
    assert b"10;RTS;0a1b2c;0;DOWN;\n" in writer.written

    # 5. Dispatcher updates
    # Dispatcher UP
    dispatcher_send(hass, "rflink_update_RTS_0a1b2c_0", {"CMD": "UP"})
    await hass.async_block_till_done()
    state = hass.states.get("cover.living_room_blinds")
    assert state.state == "opening"
    assert state.attributes.get("movement_state") == "opening"

    # Dispatcher STOP
    dispatcher_send(hass, "rflink_update_RTS_0a1b2c_0", {"CMD": "STOP"})
    await hass.async_block_till_done()
    state = hass.states.get("cover.living_room_blinds")
    assert state.state == "unknown"
    assert state.attributes.get("movement_state") == "stopped"

    # Dispatcher DOWN
    dispatcher_send(hass, "rflink_update_RTS_0a1b2c_0", {"CMD": "DOWN"})
    await hass.async_block_till_done()
    state = hass.states.get("cover.living_room_blinds")
    assert state.state == "closing"
    assert state.attributes.get("movement_state") == "closing"

    # Dispatcher unknown command (should be ignored)
    dispatcher_send(hass, "rflink_update_RTS_0a1b2c_0", {"CMD": "UNKNOWN"})
    await hass.async_block_till_done()
    state = hass.states.get("cover.living_room_blinds")
    assert state.state == "closing"


async def test_cover_inverted(hass, mock_serial_connection):
    """Test inverted cover commands and dispatcher events."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={
            "covers": {
                "RTS_0a1b2c_1": {
                    "name": "Inverted Blinds",
                    "inverted": True,
                }
            },
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await asyncio.sleep(0.01)

    writer = mock_serial_connection["writer"]

    # Inverted Open -> sends DOWN frame
    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.inverted_blinds"},
        blocking=True,
    )
    state = hass.states.get("cover.inverted_blinds")
    assert state.state == "opening"
    assert b"10;RTS;0a1b2c;1;DOWN;\n" in writer.written

    # Inverted Close -> sends UP frame
    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": "cover.inverted_blinds"},
        blocking=True,
    )
    state = hass.states.get("cover.inverted_blinds")
    assert state.state == "closing"
    assert b"10;RTS;0a1b2c;1;UP;\n" in writer.written

    # Inverted dispatcher UP -> direction is inverted, so it's closing
    dispatcher_send(hass, "rflink_update_RTS_0a1b2c_1", {"CMD": "UP"})
    await hass.async_block_till_done()
    state = hass.states.get("cover.inverted_blinds")
    assert state.state == "closing"

    # Inverted dispatcher DOWN -> direction is inverted, so it's opening
    dispatcher_send(hass, "rflink_update_RTS_0a1b2c_1", {"CMD": "DOWN"})
    await hass.async_block_till_done()
    state = hass.states.get("cover.inverted_blinds")
    assert state.state == "opening"


async def test_cover_string_config_and_short_id(hass, mock_serial_connection):
    """Test cover initialized with string config and non-standard device ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={
            "covers": {
                "ShortId": "Simple Cover",
            },
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await asyncio.sleep(0.01)

    state = hass.states.get("cover.simple_cover")
    assert state is not None
    assert state.attributes.get("friendly_name") == "Simple Cover"

    # Stop command sends default 'Unknown' and '0' protocol values
    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": "cover.simple_cover"},
        blocking=True,
    )
    writer = mock_serial_connection["writer"]
    assert b"10;Unknown;0;0;STOP;\n" in writer.written


async def test_cover_restore_state(hass, mock_serial_connection):
    """Test restoring cover state upon addition."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={
            "covers": {
                "RTS_0a1b2c_0": {
                    "name": "Restored Cover",
                    "inverted": False,
                }
            },
        },
    )
    entry.add_to_hass(hass)

    # Mock previous state as 'opening'
    with patch(
        "homeassistant.helpers.restore_state.RestoreEntity.async_get_last_state",
        return_value=State("cover.restored_cover", "opening"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await asyncio.sleep(0.01)

    state = hass.states.get("cover.restored_cover")
    assert state is not None
    assert state.state == "opening"
    assert state.attributes.get("movement_state") == "opening"


async def test_cover_send_error_handled(hass, mock_serial_connection):
    """Test exception when sending command is handled gracefully."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={
            "covers": {
                "RTS_0a1b2c_0": "Error Cover",
            },
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await asyncio.sleep(0.01)

    data = hass.data[DOMAIN][entry.entry_id]
    with patch.object(
        data, "async_send_command", side_effect=Exception("Serial write failed")
    ):
        # Should not raise exception
        await hass.services.async_call(
            "cover",
            "open_cover",
            {"entity_id": "cover.error_cover"},
            blocking=True,
        )
