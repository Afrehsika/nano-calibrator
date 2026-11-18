"""Motor configuration and live ESC output telemetry models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MotorConfig:
    """ESC PWM output limits and Quad-X motor configuration."""

    min_us: int = 1000
    idle_us: int = 1080
    max_us: int = 2000
    test_max_us: int = 1250
    esc_calibrated: bool = False
    spin_directions: list[str] = field(default_factory=lambda: ["CW", "CCW", "CW", "CCW"])

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not (900 <= self.min_us < self.idle_us < self.max_us <= 2100):
            errors.append(
                f"Motor PWM range must satisfy 900 <= min ({self.min_us}) "
                f"< idle ({self.idle_us}) < max ({self.max_us}) <= 2100."
            )
        if not (self.min_us <= self.test_max_us <= 1400):
            errors.append(
                f"Safe motor test cap ({self.test_max_us} us) must be between min ({self.min_us}) and 1400 us."
            )
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_us": int(self.min_us),
            "idle_us": int(self.idle_us),
            "max_us": int(self.max_us),
            "test_max_us": int(self.test_max_us),
            "esc_cal": bool(self.esc_calibrated),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MotorConfig":
        return cls(
            min_us=int(data.get("min_us", 1000)),
            idle_us=int(data.get("idle_us", 1080)),
            max_us=int(data.get("max_us", 2000)),
            test_max_us=int(data.get("test_max_us", 1250)),
            esc_calibrated=bool(data.get("esc_cal", False)),
        )


@dataclass
class MotorOutputs:
    """Live PWM pulse widths (us) sent to the four Quad-X motors."""

    m1_us: int = 1000  # Front-Left (CW)
    m2_us: int = 1000  # Front-Right (CCW)
    m3_us: int = 1000  # Rear-Right (CW)
    m4_us: int = 1000  # Rear-Left (CCW)
    test_active: bool = False
    test_motor: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MotorOutputs":
        motors = data.get("m", [1000, 1000, 1000, 1000])
        if len(motors) < 4:
            motors = list(motors) + [1000] * (4 - len(motors))
        return cls(
            m1_us=int(motors[0]),
            m2_us=int(motors[1]),
            m3_us=int(motors[2]),
            m4_us=int(motors[3]),
            test_active=bool(data.get("test", False)),
            test_motor=data.get("test_m"),
        )

