"""The RFLink UI integration."""
import asyncio
import logging
import serial_asyncio
from dataclasses import dataclass

from collections import deque

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send

_LOGGER = logging.getLogger(__name__)

DOMAIN = "rflink_ui"
PLATFORMS: list[Platform] = [Platform("radio_frequency"), Platform.SWITCH, Platform.SENSOR, Platform.BINARY_SENSOR]

@dataclass
class RFLinkData:
    """Class to hold RFLink data."""
    writer: asyncio.StreamWriter | None
    reader: asyncio.StreamReader | None
    recent_unknown_devices: deque
    reconnect_task: asyncio.Task | None
    keep_alive_task: asyncio.Task | None
    is_connected: bool

    async def async_send_command(self, command: str) -> None:
        """Send an RF command via RFLink safely."""
        if not self.writer or not self.is_connected:
            _LOGGER.error("Cannot send command, RFLink is disconnected")
            return
            
        _LOGGER.debug("Sending RF command: %s", command.strip())
        try:
            self.writer.write(command.encode("utf-8"))
            await self.writer.drain()
        except Exception as err:
            _LOGGER.error("Failed to send RF command: %s", err)
            raise

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RFLink UI from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    data = RFLinkData(
        writer=None,
        reader=None,
        recent_unknown_devices=deque(maxlen=50),
        reconnect_task=None,
        keep_alive_task=None,
        is_connected=False,
    )
    hass.data[DOMAIN][entry.entry_id] = data

    data.reconnect_task = hass.loop.create_task(
        _async_connection_loop(hass, entry)
    )

    # Clean up orphaned entities and devices (if user removed them in OptionsFlow)
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    
    active_devices = set(entry.options.get("switches", {}).keys()) | set(entry.options.get("sensors", {}).keys())
    
    for ent in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        is_active = any(ent.unique_id.endswith(active) for active in active_devices)
        if not is_active:
            ent_reg.async_remove(ent.entity_id)
            
    for dev in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        is_active = False
        for identifier in dev.identifiers:
            if identifier[0] == DOMAIN and identifier[1] in active_devices:
                is_active = True
                break
        if not is_active:
            dev_reg.async_remove_device(dev.id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True

async def _async_connection_loop(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Maintain the serial connection and reconnect on failure."""
    port = entry.data[CONF_PORT]
    baudrate = 57600
    
    while True:
        data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if not data:
            break
            
        try:
            reader, writer = await serial_asyncio.open_serial_connection(url=port, baudrate=baudrate)
            _LOGGER.info("Connected to RFLink on %s", port)
            
            data.reader = reader
            data.writer = writer
            data.is_connected = True
            async_dispatcher_send(hass, f"rflink_connection_{entry.entry_id}", True)
            
            # Start keep-alive
            data.keep_alive_task = hass.loop.create_task(_async_keep_alive(hass, entry.entry_id))
            
            # Read until error
            await _async_read_serial(hass, entry.entry_id, reader)
            
        except asyncio.CancelledError:
            break
        except Exception as err:
            _LOGGER.error("RFLink connection lost on %s: %s", port, err)
            
        # Cleanup before reconnect
        data.is_connected = False
        async_dispatcher_send(hass, f"rflink_connection_{entry.entry_id}", False)
        
        if data.keep_alive_task:
            data.keep_alive_task.cancel()
            data.keep_alive_task = None
            
        if data.writer:
            try:
                data.writer.close()
                await data.writer.wait_closed()
            except (ConnectionError, asyncio.TimeoutError):
                pass
            except Exception as e:
                _LOGGER.debug("Error while closing writer: %s", e)
            data.writer = None
            
        _LOGGER.info("Attempting to reconnect to RFLink in 5 seconds...")
        await asyncio.sleep(5)

async def _async_keep_alive(hass: HomeAssistant, entry_id: str) -> None:
    """Send ping every 60 seconds."""
    while True:
        await asyncio.sleep(60)
        data = hass.data.get(DOMAIN, {}).get(entry_id)
        if not data or not data.writer or not data.is_connected:
            break
            
        try:
            _LOGGER.debug("Sending Keep-Alive PING to RFLink")
            data.writer.write(b"10;PING;\n")
            await data.writer.drain()
        except Exception as err:
            _LOGGER.error("Error sending RFLink PING: %s", err)
            break

async def _async_read_serial(hass: HomeAssistant, entry_id: str, reader: asyncio.StreamReader) -> None:
    """Read lines from the serial port and dispatch them."""
    while True:
        try:
            line = await reader.readline()
        except Exception as err:
            _LOGGER.error("Error reading from RFLink: %s", err)
            break
            
        if not line:
            break
            
        decoded_line = line.decode("utf-8", errors="ignore").strip()
        if not decoded_line:
            continue
            
        _LOGGER.debug("Received RFLink data: %s", decoded_line)
        
        # Example RFLink message: 20;01;Kaku;ID=41;SWITCH=1;CMD=ON;
        # Example RFLink sensor: 20;3A;Oregon TempHygro;ID=0A4C;TEMP=00ba;HUM=40;BAT=OK;
        parts = decoded_line.split(";")
        if len(parts) >= 4 and parts[0] == "20":
            protocol = parts[2]
            
            data_dict = {}
            for part in parts[3:]:
                if "=" in part:
                    k, v = part.split("=", 1)
                    data_dict[k] = v
                    
            device_id = data_dict.get("ID")
            if not protocol or not device_id:
                continue
                
            if "CMD" in data_dict:
                # It's a switch
                switch = data_dict.get("SWITCH", "0")
                full_device_id = f"{protocol}_{device_id}_{switch}"
                device_type = "switch"
            else:
                # It's a sensor
                full_device_id = f"{protocol}_{device_id}"
                device_type = "sensor"
                
            _LOGGER.info("RFLink dispatcher sending to 'rflink_update_%s' with data: %s", full_device_id, data_dict)
            
            # Broadcast state change (sending the full dictionary)
            async_dispatcher_send(hass, f"rflink_update_{full_device_id}", data_dict)
            
            # Add to recent unknown devices buffer for UI learning
            data = hass.data[DOMAIN].get(entry_id)
            if data:
                buffer = data.recent_unknown_devices
                recent_dict = dict(buffer)
                
                # Remove it if it exists so it moves to the end of the dict (most recent)
                if full_device_id in recent_dict:
                    del recent_dict[full_device_id]
                    
                recent_dict[full_device_id] = {"type": device_type, "data": data_dict}
                data.recent_unknown_devices = deque(recent_dict.items(), maxlen=50)

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        
        if data.reconnect_task:
            data.reconnect_task.cancel()
            
        if data.keep_alive_task:
            data.keep_alive_task.cancel()
            
        if data.writer:
            data.writer.close()
            try:
                await data.writer.wait_closed()
            except (ConnectionError, asyncio.TimeoutError):
                pass
            except Exception as err:
                _LOGGER.warning("Error closing serial connection: %s", err)

    return unload_ok
