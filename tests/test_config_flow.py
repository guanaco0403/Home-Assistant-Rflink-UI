from unittest.mock import MagicMock, patch
from collections import deque

from homeassistant import config_entries
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rflink_ui.config_flow import DOMAIN


async def test_config_flow_success(hass, mock_serial_connection):
    """Test successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    # Submit port
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"port": "COM1"},
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "RFLink (COM1)"
    assert result["data"] == {"port": "COM1"}


async def test_config_flow_failure(hass, mock_serial_connection):
    """Test user config flow handles serial check failure."""
    # Make the serial port check fail
    mock_serial_connection["serial_class"].side_effect = Exception(
        "Failed to open port"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Submit port
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"port": "COM1"},
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow_manual(hass, mock_serial_connection):
    """Test adding a device manually via options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={"switches": {}, "sensors": {}},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "menu"
    assert result["step_id"] == "init"

    # Select add_manual step
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_manual"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "add_manual"

    # Add a Switch manually
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "device_type": "Switch",
            "device_id": "Kaku_123_1",
            "name": "My Switch",
        },
    )
    assert result["type"] == "create_entry"
    assert entry.options["switches"] == {"Kaku_123_1": "My Switch"}


async def test_options_flow_add_learned(hass, mock_serial_connection):
    """Test adding a recently seen/learned device via options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={"switches": {}, "sensors": {}},
    )
    entry.add_to_hass(hass)

    # Populate recent unknown devices in hass.data
    mock_data = MagicMock()
    mock_data.recent_unknown_devices = deque(
        [
            ("Kaku_learned_1", {"type": "switch", "data": {}}),
            ("Oregon_learned_2", {"type": "sensor", "data": {}}),
        ]
    )
    hass.data[DOMAIN] = {entry.entry_id: mock_data}

    # 1. Test adding a Switch (needs select_type step)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_learned"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "add_learned"

    # Submit selection of switch
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "device_id": "Kaku_learned_1",
            "name": "Learned Switch",
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "select_type"

    # Choose "Switch" and submit
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"device_type": "Switch"},
    )
    assert result["type"] == "create_entry"
    assert entry.options["switches"] == {"Kaku_learned_1": "Learned Switch"}

    # 2. Test adding a Sensor (directly added, no select_type step)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_learned"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "add_learned"

    # Submit selection of sensor
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "device_id": "Oregon_learned_2",
            "name": "Learned Sensor",
        },
    )
    assert result["type"] == "create_entry"
    assert entry.options["sensors"] == {"Oregon_learned_2": "Learned Sensor"}


async def test_options_flow_modify_and_remove(hass, mock_serial_connection):
    """Test modifying and removing a device in options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={
            "switches": {"Kaku_old_1": "Old Switch"},
            "sensors": {"Oregon_old_2": "Old Sensor"},
        },
    )
    entry.add_to_hass(hass)

    # 1. Test Modify
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "modify"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "modify"

    # Modify the ID of the switch
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "device_id": "[Switch] Kaku_old_1",
            "new_device_id": "Kaku_new_1",
        },
    )
    assert result["type"] == "create_entry"
    assert "Kaku_old_1" not in entry.options["switches"]
    assert entry.options["switches"]["Kaku_new_1"] == "Old Switch"

    # 2. Test Remove
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "remove"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "remove"

    # Remove the sensor
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "device_id": "[Sensor] Oregon_old_2",
        },
    )
    assert result["type"] == "create_entry"
    assert "Oregon_old_2" not in entry.options["sensors"]


async def test_config_flow_with_by_id_ports(hass, mock_serial_connection):
    """Test config flow lists and allows selecting by-id ports."""
    with patch(
        "glob.glob",
        return_value=["/dev/serial/by-id/usb-RFLink_gateway_1234-if00-port0"],
    ) as mock_glob:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        # Submit the by-id port
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"port": "/dev/serial/by-id/usb-RFLink_gateway_1234-if00-port0"},
        )
        assert result["type"] == "create_entry"
        assert (
            result["title"]
            == "RFLink (/dev/serial/by-id/usb-RFLink_gateway_1234-if00-port0)"
        )
        assert result["data"] == {
            "port": "/dev/serial/by-id/usb-RFLink_gateway_1234-if00-port0"
        }
        mock_glob.assert_called_once_with("/dev/serial/by-id/*")


async def test_config_flow_manual_port(hass, mock_serial_connection):
    """Test config flow with manual port entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    # Select "Enter manually"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"port": "Enter manually"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "manual_port"

    # Submit a custom port
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"port": "/dev/custom_port_path"},
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "RFLink (/dev/custom_port_path)"
    assert result["data"] == {"port": "/dev/custom_port_path"}


async def test_config_flow_manual_port_failure(hass, mock_serial_connection):
    """Test config flow with manual port entry failing serial check."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    # Select "Enter manually"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"port": "Enter manually"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "manual_port"

    # Make the serial port check fail
    mock_serial_connection["serial_class"].side_effect = Exception(
        "Failed to open port"
    )

    # Submit a custom port
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"port": "/dev/custom_port_path"},
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow_manual_light(hass, mock_serial_connection):
    """Test adding a light manually via options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={"switches": {}, "sensors": {}, "lights": {}},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "menu"
    assert result["step_id"] == "init"

    # Select add_manual step
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_manual"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "add_manual"

    # Add a Light manually
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "device_type": "Light",
            "device_id": "Kaku_123_1",
            "name": "My Dimmer",
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "light_options"

    # Choose type and submit
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "type": "dimmable",
        },
    )
    assert result["type"] == "create_entry"
    assert entry.options["lights"] == {
        "Kaku_123_1": {"name": "My Dimmer", "type": "dimmable"}
    }


async def test_options_flow_add_learned_light(hass, mock_serial_connection):
    """Test adding a recently seen/learned light via options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "COM1"},
        options={"switches": {}, "sensors": {}, "lights": {}},
    )
    entry.add_to_hass(hass)

    # Populate recent unknown devices in hass.data
    mock_data = MagicMock()
    mock_data.recent_unknown_devices = deque(
        [
            ("Kaku_learned_1", {"type": "switch", "data": {}}),
        ]
    )
    hass.data[DOMAIN] = {entry.entry_id: mock_data}

    result = await hass.config_entries.options.async_init(entry.entry_id)

    # Select add_learned step
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_learned"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "add_learned"

    # Submit selection of Light ID
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "device_id": "Kaku_learned_1",
            "name": "Learned Dimmer",
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "select_type"

    # Select device type as Light
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"device_type": "Light"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "light_options"

    # Choose type and submit
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "type": "hybrid",
        },
    )
    assert result["type"] == "create_entry"
    assert entry.options["lights"] == {
        "Kaku_learned_1": {"name": "Learned Dimmer", "type": "hybrid"}
    }
