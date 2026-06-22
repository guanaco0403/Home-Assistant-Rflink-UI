import asyncio

from homeassistant.const import STATE_OFF, STATE_ON
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rflink_ui import DOMAIN


async def test_light_setup_and_control(hass, mock_serial_connection):
    """Test setting up a light, receiving updates, and controlling it."""
    # Define a light in options
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={
            "lights": {
                "Unitec_1a4a_4": {"name": "Living Room Dimmer", "type": "dimmable"},
                "NewKaku_234_2": {"name": "Bedroom Dimmer", "type": "hybrid"},
                "Kaku_345_3": {"name": "Kitchen Light", "type": "switchable"},
                "Livolo_456_4": {"name": "Living Room Livolo", "type": "toggle"},
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
    state = hass.states.get("light.living_room_dimmer")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes.get("friendly_name") == "Living Room Dimmer"
    assert state.attributes.get("brightness") is None

    # 2. Simulate dispatcher update (Turn ON)
    from homeassistant.helpers.dispatcher import dispatcher_send

    dispatcher_send(hass, "rflink_update_Unitec_1a4a_4", {"CMD": "ON"})
    await hass.async_block_till_done()

    state = hass.states.get("light.living_room_dimmer")
    assert state.state == STATE_ON

    # Simulate dispatcher update (SET_LEVEL)
    dispatcher_send(hass, "rflink_update_Unitec_1a4a_4", {"CMD": "SET_LEVEL=10"})
    await hass.async_block_till_done()

    state = hass.states.get("light.living_room_dimmer")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 170  # 10 * 17

    # Simulate dispatcher update (raw level digit)
    dispatcher_send(hass, "rflink_update_Unitec_1a4a_4", {"CMD": "15"})
    await hass.async_block_till_done()

    state = hass.states.get("light.living_room_dimmer")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 255  # 15 * 17

    # Simulate dispatcher update (Turn OFF)
    dispatcher_send(hass, "rflink_update_Unitec_1a4a_4", {"CMD": "OFF"})
    await hass.async_block_till_done()

    state = hass.states.get("light.living_room_dimmer")
    assert state.state == STATE_OFF

    # 3. Control via service calls (Turn ON - Dimmable type)
    writer = mock_serial_connection["writer"]
    writer.written.clear()

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.living_room_dimmer"},
        blocking=True,
    )
    state = hass.states.get("light.living_room_dimmer")
    assert state.state == STATE_ON
    assert b"10;Unitec;1a4a;4;ON;\n" in writer.written

    # Set Brightness (Dimmable type)
    writer.written.clear()
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.living_room_dimmer", "brightness": 170},
        blocking=True,
    )
    state = hass.states.get("light.living_room_dimmer")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 170
    assert b"10;Unitec;1a4a;4;10;\n" in writer.written

    # Turn OFF
    writer.written.clear()
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.living_room_dimmer"},
        blocking=True,
    )
    state = hass.states.get("light.living_room_dimmer")
    assert state.state == STATE_OFF
    assert b"10;Unitec;1a4a;4;OFF;\n" in writer.written

    # 4. Control Hybrid Dimmer (Bedroom Dimmer)
    writer.written.clear()
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.bedroom_dimmer", "brightness": 170},
        blocking=True,
    )
    state = hass.states.get("light.bedroom_dimmer")
    assert state.state == STATE_ON
    # For hybrid type, it sends level (10) followed by ON
    assert b"10;NewKaku;234;2;10;\n" in writer.written
    assert b"10;NewKaku;234;2;ON;\n" in writer.written

    # 5. Switchable light type
    state = hass.states.get("light.kitchen_light")
    assert state is not None
    assert state.state == STATE_OFF
    assert "onoff" in state.attributes.get("supported_color_modes")

    writer.written.clear()
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.kitchen_light"},
        blocking=True,
    )
    state = hass.states.get("light.kitchen_light")
    assert state.state == STATE_ON
    assert b"10;Kaku;345;3;ON;\n" in writer.written

    writer.written.clear()
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.kitchen_light"},
        blocking=True,
    )
    state = hass.states.get("light.kitchen_light")
    assert state.state == STATE_OFF
    assert b"10;Kaku;345;3;OFF;\n" in writer.written

    # 6. Toggle light type
    state = hass.states.get("light.living_room_livolo")
    assert state is not None
    assert state.state == STATE_OFF
    assert "onoff" in state.attributes.get("supported_color_modes")

    # Turn ON (Toggle type sends ON)
    writer.written.clear()
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.living_room_livolo"},
        blocking=True,
    )
    state = hass.states.get("light.living_room_livolo")
    assert state.state == STATE_ON
    assert b"10;Livolo;456;4;ON;\n" in writer.written

    # Turn OFF (Toggle type sends ON)
    writer.written.clear()
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.living_room_livolo"},
        blocking=True,
    )
    state = hass.states.get("light.living_room_livolo")
    assert state.state == STATE_OFF
    assert b"10;Livolo;456;4;ON;\n" in writer.written

    # Test toggle state updates via dispatcher
    dispatcher_send(hass, "rflink_update_Livolo_456_4", {"CMD": "ON"})
    await hass.async_block_till_done()
    state = hass.states.get("light.living_room_livolo")
    assert state.state == STATE_ON
