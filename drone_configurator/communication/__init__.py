"""Serial communication protocol, background worker, and virtual FC simulator."""

from .protocol import (
    PROTOCOL_VERSION,
    CommandType,
    MessageType,
    ProtocolError,
    ProtocolMessage,
    build_command,
    parse_line,
)
from .serial_manager import SerialManager

__all__ = [
    "PROTOCOL_VERSION",
    "CommandType",
    "MessageType",
    "ProtocolError",
    "ProtocolMessage",
    "build_command",
    "parse_line",
    "SerialManager",
]

