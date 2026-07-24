from collections import deque
from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rflink_ui.config_flow import DOMAIN


async def test_options_flow_add_cover_manual(hass, mock_serial_connection):
    """Test adding a cover manually via the options flow (two-step: type + inverted)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={"switches": {}, "sensors": {}, "covers": {}},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_manual"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "add_manual"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "device_type": "Cover",
            "device_id": "Somfy_1a4a_1",
            "name": "Kitchen Shutter",
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "cover_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"inverted": True},
    )
    assert result["type"] == "create_entry"
    assert entry.options["covers"] == {
        "Somfy_1a4a_1": {"name": "Kitchen Shutter", "inverted": True}
    }


async def test_options_flow_add_learned_offers_cover(hass, mock_serial_connection):
    """A learned CMD-type device must offer Switch, Binary Sensor and Cover."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={"switches": {}, "sensors": {}, "covers": {}},
    )
    entry.add_to_hass(hass)

    mock_data = MagicMock()
    mock_data.recent_unknown_devices = deque(
        [("Somfy_learned_1", {"type": "switch", "data": {}})]
    )
    hass.data[DOMAIN] = {entry.entry_id: mock_data}

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_learned"},
    )
    assert result["type"] == "form"
    schema_options = result["data_schema"].schema["device_id"].container
    assert "[Switch] Somfy_learned_1" in schema_options
    assert "[Binary Sensor] Somfy_learned_1" in schema_options
    assert "[Cover] Somfy_learned_1" in schema_options

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "device_id": "[Cover] Somfy_learned_1",
            "name": "Learned Cover",
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "cover_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"inverted": False},
    )
    assert result["type"] == "create_entry"
    assert entry.options["covers"] == {
        "Somfy_learned_1": {"name": "Learned Cover", "inverted": False}
    }


async def test_options_flow_modify_and_remove_cover(hass, mock_serial_connection):
    """Test modifying and removing a cover in the options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={
            "switches": {},
            "sensors": {},
            "covers": {
                "Somfy_old_1": {"name": "Old Shutter", "inverted": False}
            },
        },
    )
    entry.add_to_hass(hass)

    # Modify
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "modify"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "device_id": "[Cover] Somfy_old_1",
            "new_device_id": "Somfy_new_1",
        },
    )
    assert result["type"] == "create_entry"
    assert "Somfy_old_1" not in entry.options["covers"]
    assert entry.options["covers"]["Somfy_new_1"] == {
        "name": "Old Shutter",
        "inverted": False,
    }

    # Remove
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "remove"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"device_id": "[Cover] Somfy_new_1"},
    )
    assert result["type"] == "create_entry"
    assert "Somfy_new_1" not in entry.options["covers"]
