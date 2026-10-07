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
    """Mock serial / serialx connection and discovery."""
    reader = MockStreamReader()
    writer = MockStreamWriter()

    # Mock open_serial_connection
    async def mock_open(url, baudrate, **kwargs):
        return reader, writer

    # Mock serial.Serial / serialx.serial_for_url
    mock_serial_instance = MagicMock()
    mock_serial_instance.__enter__.return_value = mock_serial_instance

    mock_serial_class = MagicMock(return_value=mock_serial_instance)

    def mock_serialx_for_url(*args, **kwargs):
        if mock_serial_class.side_effect:
            if isinstance(mock_serial_class.side_effect, type) and issubclass(
                mock_serial_class.side_effect, BaseException
            ):
                raise mock_serial_class.side_effect()
            if isinstance(mock_serial_class.side_effect, BaseException):
                raise mock_serial_class.side_effect
            if callable(mock_serial_class.side_effect):
                return mock_serial_class.side_effect(*args, **kwargs)
        return mock_serial_instance

    with patch("serial.Serial", mock_serial_class), patch(
        "serial.tools.list_ports.comports", return_value=[MagicMock(device="COM1")]
    ), patch(
        "serial_asyncio.open_serial_connection", side_effect=mock_open
    ) as mock_open_conn, patch(
        "serialx.serial_for_url", side_effect=mock_serialx_for_url
    ) as mock_serialx_url, patch(
        "serialx.list_serial_ports", return_value=[MagicMock(device="COM1")]
    ), patch(
        "serialx.open_serial_connection", side_effect=mock_open
    ) as mock_serialx_open_conn:

        yield {
            "serial_class": mock_serial_class,
            "serial_instance": mock_serial_instance,
            "serialx_for_url": mock_serialx_url,
            "open_serial_connection": mock_open_conn,
            "serialx_open_connection": mock_serialx_open_conn,
            "reader": reader,
            "writer": writer,
        }
