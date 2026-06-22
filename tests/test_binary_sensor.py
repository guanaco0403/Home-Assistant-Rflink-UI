import asyncio

from homeassistant.const import STATE_OFF, STATE_ON
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rflink_ui import DOMAIN


async def test_connection_binary_sensor(hass, mock_serial_connection):
    """Test the RFLink connection status binary sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={"switches": {}, "sensors": {}},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await asyncio.sleep(0.01)

    # 1. Verify connection status sensor was created and is ON (since serial connected successfully in mock)
    state = hass.states.get("binary_sensor.rflink_com1_connection_status")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get("device_class") == "connectivity"

    # 2. Simulate disconnection dispatcher signal
    from homeassistant.helpers.dispatcher import dispatcher_send
    dispatcher_send(
        hass,
        f"rflink_connection_{entry.entry_id}",
        False
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.rflink_com1_connection_status")
    assert state.state == STATE_OFF

    # 3. Simulate reconnection dispatcher signal
    dispatcher_send(
        hass,
        f"rflink_connection_{entry.entry_id}",
        True
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.rflink_com1_connection_status")
    assert state.state == STATE_ON
