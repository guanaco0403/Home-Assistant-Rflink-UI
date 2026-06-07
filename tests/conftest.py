import pytest
import asyncio
from unittest.mock import MagicMock, patch

# Enable loading of custom integrations
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


class MockStreamReader:
    """Mock StreamReader that reads from an asyncio.Queue."""
    def __init__(self):
        self.queue = asyncio.Queue()

    async def readline(self) -> bytes:
        # This will block until feed_data is called
        return await self.queue.get()

    def feed_data(self, data: bytes) -> None:
        self.queue.put_nowait(data)

    def feed_line(self, line: str) -> None:
        if not line.endswith("\n"):
            line += "\n"
        self.feed_data(line.encode("utf-8"))


class MockStreamWriter:
    """Mock StreamWriter that records written bytes."""
    def __init__(self):
        self.written = []
        self._closed = False

    def write(self, data: bytes) -> None:
        self.written.append(data)

    async def drain(self) -> None:
        await asyncio.sleep(0.001)

    def close(self) -> None:
        self._closed = True

    async def wait_closed(self) -> None:
        await asyncio.sleep(0.001)


@pytest.fixture
def mock_serial_connection():
    """Mock open_serial_connection and serial.Serial."""
    reader = MockStreamReader()
    writer = MockStreamWriter()

    # Mock serial_asyncio.open_serial_connection
    async def mock_open(url, baudrate, **kwargs):
        return reader, writer

    # Mock serial.Serial (used in config flow validation)
    mock_serial_instance = MagicMock()
    mock_serial_instance.__enter__.return_value = mock_serial_instance

    with patch("serial.Serial", return_value=mock_serial_instance) as mock_serial_class, \
         patch("serial.tools.list_ports.comports", return_value=[MagicMock(device="COM1")]), \
         patch("serial_asyncio.open_serial_connection", side_effect=mock_open) as mock_open_conn:
        
        yield {
            "serial_class": mock_serial_class,
            "serial_instance": mock_serial_instance,
            "open_serial_connection": mock_open_conn,
            "reader": reader,
            "writer": writer,
        }
