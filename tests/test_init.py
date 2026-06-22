import asyncio

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rflink_ui import DOMAIN, RFLinkData


async def test_setup_unload_entry(hass, mock_serial_connection):
    """Test setting up and unloading the integration entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={"switches": {}, "sensors": {}},
    )
    entry.add_to_hass(hass)

    # Setup the entry
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify connection was established (mocked) and state is loaded
    assert entry.state is ConfigEntryState.LOADED
    data = hass.data[DOMAIN][entry.entry_id]
    assert isinstance(data, RFLinkData)
    
    # Wait a small amount of time for the connection loop to run open_serial_connection
    await asyncio.sleep(0.01)
    assert data.is_connected is True

    # Unload the entry
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data[DOMAIN]


async def test_serial_read_and_dispatch(hass, mock_serial_connection):
    """Test reading from serial and dispatching updates to HA."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={"switches": {}, "sensors": {}},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await asyncio.sleep(0.01)

    data = hass.data[DOMAIN][entry.entry_id]
    
    # Verify dispatcher is called when we write to the mock reader
    # We will simulate receiving a switch command from RFLink
    # Message: 20;01;Kaku;ID=41;SWITCH=1;CMD=ON;
    mock_serial_connection["reader"].feed_line("20;01;Kaku;ID=41;SWITCH=1;CMD=ON;")
    
    # Let the serial reader task process the line
    await asyncio.sleep(0.01)

    # Check if the device was added to the recent unknown devices deque
    assert len(data.recent_unknown_devices) == 1
    device_id, info = data.recent_unknown_devices[0]
    assert device_id == "Kaku_41_1"
    assert info["type"] == "switch"
    assert info["data"]["CMD"] == "ON"

    # Simulate receiving sensor data
    # Message: 20;3A;Oregon TempHygro;ID=0A4C;TEMP=00ba;HUM=40;BAT=OK;
    mock_serial_connection["reader"].feed_line("20;3A;Oregon TempHygro;ID=0A4C;TEMP=00ba;HUM=40;BAT=OK;")
    await asyncio.sleep(0.01)

    assert len(data.recent_unknown_devices) == 2
    device_id, info = data.recent_unknown_devices[1] # most recent is at index 1
    assert device_id == "Oregon TempHygro_0A4C"
    assert info["type"] == "sensor"
    assert info["data"]["TEMP"] == "00ba"
    assert info["data"]["HUM"] == "40"

    # Unload
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
