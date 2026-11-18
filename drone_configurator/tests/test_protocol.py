"""Unit tests for the JSON serial protocol and virtual FC simulator."""

import json

import pytest

from communication.protocol import CommandType, MessageType, ProtocolError, build_command, parse_line
from communication.simulator import VirtualFlightController


def test_build_and_parse_ack() -> None:
    raw = build_command(CommandType.HELLO, 42)
    assert raw.endswith(b"\n")
    decoded = json.loads(raw.decode("ascii"))
    assert decoded == {"id": 42, "cmd": "hello"}

    msg = parse_line('{"type":"ack","id":42,"cmd":"hello","ok":true,"data":{"mcu":"ATmega328P"}}')
    assert msg.msg_type == MessageType.ACK
    assert msg.req_id == 42
    assert msg.ok is True
    assert msg.data["mcu"] == "ATmega328P"


def test_parse_invalid_lines() -> None:
    with pytest.raises(ProtocolError):
        parse_line("")
    with pytest.raises(ProtocolError):
        parse_line("Debug: boot complete")
    with pytest.raises(ProtocolError):
        parse_line('{"type":"unknown_type"}')


def test_simulator_safety_interlocks() -> None:
    sim = VirtualFlightController()

    # Handshake
    hello_lines = sim.handle_command(build_command(CommandType.HELLO, 1))
    ack = parse_line(hello_lines[0])
    assert ack.ok is True
    assert ack.data["mcu"] == "ATmega328P"

    # Motor test without confirm must fail
    no_confirm = sim.handle_command(build_command(CommandType.MOTOR_TEST, 2, {"motor": 1, "pwm": 1150, "confirm": False}))
    err = parse_line(no_confirm[0])
    assert err.msg_type == MessageType.ERR
    assert err.error_code == "NO_CONFIRM"

    # Motor test above test_max_us (1250) must fail
    over_cap = sim.handle_command(build_command(CommandType.MOTOR_TEST, 3, {"motor": 1, "pwm": 1500, "confirm": True}))
    err2 = parse_line(over_cap[0])
    assert err2.msg_type == MessageType.ERR
    assert err2.error_code == "PWM_LIMIT"

    # Valid motor test succeeds
    ok_test = sim.handle_command(build_command(CommandType.MOTOR_TEST, 4, {"motor": 2, "pwm": 1150, "confirm": True}))
    ack2 = parse_line(ok_test[0])
    assert ack2.ok is True

