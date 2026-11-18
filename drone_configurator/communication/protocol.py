"""Structured JSON-over-serial protocol definitions and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


PROTOCOL_VERSION = "1.0"


class CommandType(str, Enum):
    """Commands sent from the desktop configurator to the Arduino Nano FC."""

    HELLO = "hello"
    GET_CONFIG = "get_config"
    SET_PID = "set_pid"
    RESET_PID = "reset_pid"
    SAVE_EEPROM = "save_eeprom"
    CAL_START = "cal_start"
    SET_RADIO_CFG = "set_radio_cfg"
    SET_MOTOR_CFG = "set_motor_cfg"
    MOTOR_TEST = "motor_test"
    MOTOR_STOP = "motor_stop"
    SET_STREAM = "set_stream"


class MessageType(str, Enum):
    """Message types emitted by the Arduino Nano FC."""

    ACK = "ack"
    ERR = "err"
    TELEMETRY = "telemetry"
    CAL_PROGRESS = "cal_progress"


class ProtocolError(Exception):
    """Raised when a protocol message fails structural or semantic validation."""


@dataclass
class ProtocolMessage:
    """Validated incoming message from the flight controller."""

    msg_type: MessageType
    req_id: int | None = None
    cmd: str | None = None
    ok: bool = True
    data: dict[str, Any] = field(default_factory=dict)
    error_code: str = ""
    error_msg: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


def build_command(cmd: CommandType | str, req_id: int, payload: dict[str, Any] | None = None) -> bytes:
    """Serialize a validated command into a newline-terminated JSON frame."""
    cmd_str = cmd.value if isinstance(cmd, CommandType) else str(cmd)
    frame: dict[str, Any] = {"id": int(req_id), "cmd": cmd_str}
    if payload:
        frame["data"] = payload
    encoded = json.dumps(frame, separators=(",", ":"), ensure_ascii=True)
    return (encoded + "\n").encode("ascii")


def parse_line(raw_line: str) -> ProtocolMessage:
    """Parse and validate a single newline-delimited JSON line from the FC."""
    text = raw_line.strip()
    if not text:
        raise ProtocolError("Empty line")
    if not text.startswith("{"):
        raise ProtocolError(f"Non-JSON serial output: {text[:80]}")

    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"Malformed JSON: {exc}") from exc

    if not isinstance(obj, dict):
        raise ProtocolError("JSON root must be an object")

    raw_type = obj.get("type")
    try:
        msg_type = MessageType(raw_type)
    except ValueError as exc:
        raise ProtocolError(f"Unknown message type: {raw_type!r}") from exc

    req_id = obj.get("id")
    if req_id is not None and not isinstance(req_id, int):
        raise ProtocolError("Field 'id' must be an integer")

    if msg_type == MessageType.ACK:
        return ProtocolMessage(
            msg_type=msg_type,
            req_id=req_id,
            cmd=obj.get("cmd"),
            ok=bool(obj.get("ok", True)),
            data=obj.get("data") if isinstance(obj.get("data"), dict) else {},
            raw=obj,
        )

    if msg_type == MessageType.ERR:
        return ProtocolMessage(
            msg_type=msg_type,
            req_id=req_id,
            cmd=obj.get("cmd"),
            ok=False,
            error_code=str(obj.get("code", "UNKNOWN")),
            error_msg=str(obj.get("msg", "Unknown firmware error")),
            raw=obj,
        )

    return ProtocolMessage(
        msg_type=msg_type,
        req_id=req_id,
        data=obj,
        raw=obj,
    )

