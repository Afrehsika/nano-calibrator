"""Unit tests for PID, Radio, and Motor configuration models."""

from models.motor_config import MotorConfig
from models.pid_config import AxisPID, PIDConfig
from models.radio_data import ChannelConfig, RadioConfig


def test_pid_validation() -> None:
    cfg = PIDConfig.defaults()
    assert cfg.validate() == []

    bad = PIDConfig.defaults()
    bad.rate.roll = AxisPID(-1.0, 0.0, 0.0)
    errors = bad.validate()
    assert len(errors) == 1
    assert "Rate Roll P" in errors[0]


def test_radio_validation() -> None:
    cfg = RadioConfig()
    assert cfg.validate() == []

    cfg.roll = ChannelConfig("Roll", min_us=1600, center_us=1500, max_us=2000)
    errors = cfg.validate()
    assert len(errors) == 1


def test_motor_validation() -> None:
    cfg = MotorConfig()
    assert cfg.validate() == []

    cfg.test_max_us = 1800
    errors = cfg.validate()
    assert len(errors) == 1

