import asyncio

from homeassistant.helpers.dispatcher import dispatcher_send
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rflink_ui import DOMAIN


async def test_cover_setup_and_control(hass, mock_serial_connection):
    """Test setting up a cover, receiving remote updates, and controlling it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={
            "switches": {},
            "sensors": {},
            "covers": {"Somfy_1a4a_1": {"name": "Kitchen Shutter", "inverted": False}},
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await asyncio.sleep(0.01)

    # 1. Verify entity creation - default assumed state is closed
    state = hass.states.get("cover.kitchen_shutter")
    assert state is not None
    assert state.state == "closed"
    assert state.attributes.get("friendly_name") == "Kitchen Shutter"
    assert state.attributes.get("device_class") == "shutter"
    assert state.attributes.get("assumed_state") is True

    # 2. A physical remote sends UP -> cover should become open
    dispatcher_send(hass, "rflink_update_Somfy_1a4a_1", {"CMD": "UP"})
    await hass.async_block_till_done()
    state = hass.states.get("cover.kitchen_shutter")
    assert state.state == "open"

    # 3. A physical remote sends DOWN -> cover should become closed
    dispatcher_send(hass, "rflink_update_Somfy_1a4a_1", {"CMD": "DOWN"})
    await hass.async_block_till_done()
    state = hass.states.get("cover.kitchen_shutter")
    assert state.state == "closed"

    # 4. STOP alone must not change the open/closed state
    dispatcher_send(hass, "rflink_update_Somfy_1a4a_1", {"CMD": "UP"})
    await hass.async_block_till_done()
    dispatcher_send(hass, "rflink_update_Somfy_1a4a_1", {"CMD": "STOP"})
    await hass.async_block_till_done()
    state = hass.states.get("cover.kitchen_shutter")
    assert state.state == "open"

    writer = mock_serial_connection["writer"]

    # 5. Control via service calls
    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": "cover.kitchen_shutter"},
        blocking=True,
    )
    state = hass.states.get("cover.kitchen_shutter")
    assert state.state == "closed"
    assert b"10;Somfy;1a4a;1;DOWN;\n" in writer.written

    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.kitchen_shutter"},
        blocking=True,
    )
    state = hass.states.get("cover.kitchen_shutter")
    assert state.state == "open"
    assert b"10;Somfy;1a4a;1;UP;\n" in writer.written

    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": "cover.kitchen_shutter"},
        blocking=True,
    )
    assert b"10;Somfy;1a4a;1;STOP;\n" in writer.written


async def test_cover_inverted_protocol(hass, mock_serial_connection):
    """Test a cover configured as inverted (eg. NewKaku) swaps UP/DOWN."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={
            "switches": {},
            "sensors": {},
            "covers": {
                "NewKaku_abc_1": {"name": "Bedroom Blind", "inverted": True}
            },
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await asyncio.sleep(0.01)

    writer = mock_serial_connection["writer"]

    # Opening an inverted cover must send DOWN on the wire.
    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.bedroom_blind"},
        blocking=True,
    )
    state = hass.states.get("cover.bedroom_blind")
    assert state.state == "open"
    assert b"10;NewKaku;abc;1;DOWN;\n" in writer.written

    # Closing an inverted cover must send UP on the wire.
    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": "cover.bedroom_blind"},
        blocking=True,
    )
    state = hass.states.get("cover.bedroom_blind")
    assert state.state == "closed"
    assert b"10;NewKaku;abc;1;UP;\n" in writer.written

    # A remote's raw UP command must be interpreted as "closed" (inverted).
    dispatcher_send(hass, "rflink_update_NewKaku_abc_1", {"CMD": "UP"})
    await hass.async_block_till_done()
    state = hass.states.get("cover.bedroom_blind")
    assert state.state == "closed"


async def test_cover_restores_last_state(hass, mock_serial_connection):
    """Test that a cover restores its last known open/closed state on restart."""
    from homeassistant.core import State
    from pytest_homeassistant_custom_component.common import mock_restore_cache

    mock_restore_cache(hass, [State("cover.restored_shutter", "open")])

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={
            "switches": {},
            "sensors": {},
            "covers": {"Somfy_9999_1": "Restored Shutter"},
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await asyncio.sleep(0.01)

    state = hass.states.get("cover.restored_shutter")
    assert state is not None
    assert state.state == "open"
