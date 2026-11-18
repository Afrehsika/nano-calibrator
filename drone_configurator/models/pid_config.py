"""PID configuration models for inner rate loop and outer angle loop."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


PID_MIN_GAIN = 0.0
PID_MAX_GAIN = 50.0


@dataclass
class AxisPID:
    """Three-term PID gains for a single control axis."""

    p: float
    i: float
    d: float

    def validate(self, axis_name: str, loop_name: str) -> list[str]:
        """Return validation errors if any gain is non-finite or out of range."""
        errors: list[str] = []
        for term, val in (("P", self.p), ("I", self.i), ("D", self.d)):
            if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
                errors.append(f"{loop_name} {axis_name} {term} must be a finite number.")
            elif val < PID_MIN_GAIN or val > PID_MAX_GAIN:
                errors.append(
                    f"{loop_name} {axis_name} {term} ({val}) must be between "
                    f"{PID_MIN_GAIN} and {PID_MAX_GAIN}."
                )
        return errors

    def to_dict(self) -> dict[str, float]:
        return {"p": round(float(self.p), 4), "i": round(float(self.i), 4), "d": round(float(self.d), 4)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AxisPID":
        return cls(
            p=float(data.get("p", 0.0)),
            i=float(data.get("i", 0.0)),
            d=float(data.get("d", 0.0)),
        )


@dataclass
class RatePID:
    """Inner rate-control loop PID gains (gyro deg/s -> motor mixer)."""

    roll: AxisPID = field(default_factory=lambda: AxisPID(1.30, 0.04, 18.0))
    pitch: AxisPID = field(default_factory=lambda: AxisPID(1.30, 0.04, 18.0))
    yaw: AxisPID = field(default_factory=lambda: AxisPID(3.00, 0.02, 0.0))

    def validate(self) -> list[str]:
        errors: list[str] = []
        errors.extend(self.roll.validate("Roll", "Rate"))
        errors.extend(self.pitch.validate("Pitch", "Rate"))
        errors.extend(self.yaw.validate("Yaw", "Rate"))
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "roll": self.roll.to_dict(),
            "pitch": self.pitch.to_dict(),
            "yaw": self.yaw.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RatePID":
        defaults = cls()
        return cls(
            roll=AxisPID.from_dict(data["roll"]) if "roll" in data else defaults.roll,
            pitch=AxisPID.from_dict(data["pitch"]) if "pitch" in data else defaults.pitch,
            yaw=AxisPID.from_dict(data["yaw"]) if "yaw" in data else defaults.yaw,
        )


@dataclass
class AnglePID:
    """Outer angle-control loop PID gains (attitude deg -> target rate)."""

    roll: AxisPID = field(default_factory=lambda: AxisPID(4.50, 0.00, 0.0))
    pitch: AxisPID = field(default_factory=lambda: AxisPID(4.50, 0.00, 0.0))
    yaw: AxisPID = field(default_factory=lambda: AxisPID(0.00, 0.00, 0.0))

    def validate(self) -> list[str]:
        errors: list[str] = []
        errors.extend(self.roll.validate("Roll", "Angle"))
        errors.extend(self.pitch.validate("Pitch", "Angle"))
        errors.extend(self.yaw.validate("Yaw", "Angle"))
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "roll": self.roll.to_dict(),
            "pitch": self.pitch.to_dict(),
            "yaw": self.yaw.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnglePID":
        defaults = cls()
        return cls(
            roll=AxisPID.from_dict(data["roll"]) if "roll" in data else defaults.roll,
            pitch=AxisPID.from_dict(data["pitch"]) if "pitch" in data else defaults.pitch,
            yaw=AxisPID.from_dict(data["yaw"]) if "yaw" in data else defaults.yaw,
        )


@dataclass
class PIDConfig:
    """Complete dual-loop PID configuration for the flight controller."""

    rate: RatePID = field(default_factory=RatePID)
    angle: AnglePID = field(default_factory=AnglePID)
    angle_loop_enabled: bool = True

    @classmethod
    def defaults(cls) -> "PIDConfig":
        return cls()

    def validate(self) -> list[str]:
        errors = self.rate.validate()
        errors.extend(self.angle.validate())
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "angle_loop_enabled": bool(self.angle_loop_enabled),
            "rate": self.rate.to_dict(),
            "angle": self.angle.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PIDConfig":
        return cls(
            angle_loop_enabled=bool(data.get("angle_loop_enabled", True)),
            rate=RatePID.from_dict(data.get("rate", {})),
            angle=AnglePID.from_dict(data.get("angle", {})),
        )

