import asyncio
import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rflink_ui import DOMAIN


async def test_radio_frequency_transmitter(hass, mock_serial_connection):
    """Test the RFLink transmitter entity and send_command service."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="RFLink COM1",
        data={"port": "COM1"},
        options={"switches": {}, "sensors": {}},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await asyncio.sleep(0.01)

    # 1. Verify transmitter entity was created
    # The domain is radio_frequency (or fallback depending on HA version)
    # Let's look up the entity in the state registry
    state = hass.states.get("radio_frequency.rflink_com1_transmitter")
    # If the domain is not radio_frequency, check if it falls back to a different domain
    if state is None:
         # Depending on pre-2026.5 version fallback, it might register as entity under DOMAIN/platform domain
         # Let's search the state registry for any entity ending with transmitter
         transmitter_states = [s for s in hass.states.async_all() if s.entity_id.endswith("transmitter")]
         assert len(transmitter_states) == 1
         state = transmitter_states[0]

    assert state is not None
    if state.entity_id.startswith("radio_frequency."):
         assert state.state == "unknown"
    else:
         assert state.state == "ready"
    assert state.attributes.get("supported_frequencies") == [433.92]

    # 2. Test send_command service call
    await hass.services.async_call(
        DOMAIN,
        "send_command",
        {
            "entity_id": state.entity_id,
            "protocol": "Kaku",
            "command": "0000abc;1;ON",
        },
        blocking=True,
    )

    # Check that the message was written to the serial interface
    # Expected format: 10;{protocol};{command};\n
    # Which translates to: 10;Kaku;0000abc;1;ON;\n
    writer = mock_serial_connection["writer"]
    assert b"10;Kaku;0000abc;1;ON;\n" in writer.written

    # Check that the state is updated
    updated_state = hass.states.get(state.entity_id)
    assert updated_state is not None
    if updated_state.entity_id.startswith("radio_frequency."):
        assert updated_state.state != "unknown"
        assert "T" in updated_state.state  # Check for ISO timestamp format
    else:
        assert updated_state.state == "ready"

