"""Radio receiver channel telemetry and endpoint configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


PWM_HARD_MIN = 800
PWM_HARD_MAX = 2200


@dataclass
class ChannelConfig:
    """Endpoint and center calibration for a single RC channel."""

    name: str
    min_us: int = 1000
    center_us: int = 1500
    max_us: int = 2000
    deadband_us: int = 10
    reversed: bool = False

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not (PWM_HARD_MIN <= self.min_us < self.center_us < self.max_us <= PWM_HARD_MAX):
            errors.append(
                f"{self.name}: endpoints must satisfy {PWM_HARD_MIN} <= min ({self.min_us}) "
                f"< center ({self.center_us}) < max ({self.max_us}) <= {PWM_HARD_MAX}."
            )
        if not (0 <= self.deadband_us <= 100):
            errors.append(f"{self.name}: deadband ({self.deadband_us} us) must be 0..100 us.")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "min": int(self.min_us),
            "center": int(self.center_us),
            "max": int(self.max_us),
            "deadband": int(self.deadband_us),
            "rev": bool(self.reversed),
        }

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "ChannelConfig":
        return cls(
            name=name,
            min_us=int(data.get("min", 1000)),
            center_us=int(data.get("center", 1500)),
            max_us=int(data.get("max", 2000)),
            deadband_us=int(data.get("deadband", 10)),
            reversed=bool(data.get("rev", False)),
        )


@dataclass
class RadioConfig:
    """Complete nRF24L01 receiver channel mapping and failsafe timeout."""

    roll: ChannelConfig = field(default_factory=lambda: ChannelConfig("Roll"))
    pitch: ChannelConfig = field(default_factory=lambda: ChannelConfig("Pitch"))
    throttle: ChannelConfig = field(default_factory=lambda: ChannelConfig("Throttle", center_us=1001))
    yaw: ChannelConfig = field(default_factory=lambda: ChannelConfig("Yaw"))
    timeout_ms: int = 500

    def validate(self) -> list[str]:
        errors: list[str] = []
        # Throttle center is typically not used as a stick neutral, allow min < center <= max or standard
        for ch in (self.roll, self.pitch, self.yaw):
            errors.extend(ch.validate())
        if not (PWM_HARD_MIN <= self.throttle.min_us < self.throttle.max_us <= PWM_HARD_MAX):
            errors.append(
                f"Throttle: min ({self.throttle.min_us}) must be < max ({self.throttle.max_us}) "
                f"within {PWM_HARD_MIN}..{PWM_HARD_MAX}."
            )
        if not (100 <= self.timeout_ms <= 5000):
            errors.append(f"Radio timeout ({self.timeout_ms} ms) must be 100..5000 ms.")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "roll": self.roll.to_dict(),
            "pitch": self.pitch.to_dict(),
            "throttle": self.throttle.to_dict(),
            "yaw": self.yaw.to_dict(),
            "timeout_ms": int(self.timeout_ms),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RadioConfig":
        defaults = cls()
        return cls(
            roll=ChannelConfig.from_dict("Roll", data["roll"]) if "roll" in data else defaults.roll,
            pitch=ChannelConfig.from_dict("Pitch", data["pitch"]) if "pitch" in data else defaults.pitch,
            throttle=ChannelConfig.from_dict("Throttle", data["throttle"]) if "throttle" in data else defaults.throttle,
            yaw=ChannelConfig.from_dict("Yaw", data["yaw"]) if "yaw" in data else defaults.yaw,
            timeout_ms=int(data.get("timeout_ms", 500)),
        )


@dataclass
class RadioData:
    """Live received joystick and RC channel values."""

    roll_us: int = 1500
    pitch_us: int = 1500
    throttle_us: int = 1000
    yaw_us: int = 1500
    joystick_x: float = 0.0
    joystick_y: float = 0.0
    rx_connected: bool = False
    last_packet_age_ms: int = 0
    packet_loss_pct: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RadioData":
        roll_us = int(data.get("roll", 1500))
        pitch_us = int(data.get("pitch", 1500))
        return cls(
            roll_us=roll_us,
            pitch_us=pitch_us,
            throttle_us=int(data.get("thr", 1000)),
            yaw_us=int(data.get("yaw", 1500)),
            joystick_x=float(data.get("jx", max(-1.0, min(1.0, (roll_us - 1500) / 500.0)))),
            joystick_y=float(data.get("jy", max(-1.0, min(1.0, (pitch_us - 1500) / 500.0)))),
            rx_connected=bool(data.get("rx", False)),
            last_packet_age_ms=int(data.get("age_ms", 0)),
            packet_loss_pct=float(data.get("loss", 0.0)),
        )

