"""Configuration profile CRUD, validation, and JSON import/export."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models.motor_config import MotorConfig
from models.pid_config import PIDConfig
from models.radio_data import RadioConfig


_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_\- ]{1,64}$")


@dataclass
class ProfileData:
    """Complete serializable drone configuration profile."""

    name: str
    pid: PIDConfig = field(default_factory=PIDConfig.defaults)
    radio: RadioConfig = field(default_factory=RadioConfig)
    motor: MotorConfig = field(default_factory=MotorConfig)
    notes: str = ""
    updated_at: str = ""

    def validate(self) -> list[str]:
        errors: list[str] = []
        errors.extend(self.pid.validate())
        errors.extend(self.radio.validate())
        errors.extend(self.motor.validate())
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "updated_at": self.updated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "notes": self.notes,
            "pid": self.pid.to_dict(),
            "radio": self.radio.to_dict(),
            "motor": self.motor.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], fallback_name: str = "Imported Profile") -> "ProfileData":
        return cls(
            name=str(data.get("name", fallback_name)),
            notes=str(data.get("notes", "")),
            updated_at=str(data.get("updated_at", "")),
            pid=PIDConfig.from_dict(data.get("pid", {})),
            radio=RadioConfig.from_dict(data.get("radio", {})),
            motor=MotorConfig.from_dict(data.get("motor", {})),
        )


class ConfigurationService:
    """Manages local JSON configuration profiles and validation."""

    def __init__(self, profiles_dir: Path) -> None:
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_default_profile()

    def _ensure_default_profile(self) -> None:
        if not list(self.profiles_dir.glob("*.json")):
            default_profile = ProfileData(
                name="Default Quad-X",
                notes="Baseline conservative PID, radio, and motor limits for 250-class Quad-X.",
            )
            self.save_profile(default_profile)

    @staticmethod
    def validate_profile_name(name: str) -> str:
        cleaned = name.strip()
        if not _SAFE_NAME_RE.match(cleaned):
            raise ValueError(
                "Profile name must be 1-64 characters using letters, numbers, spaces, '-' or '_'."
            )
        return cleaned

    def _path_for(self, name: str) -> Path:
        safe = self.validate_profile_name(name)
        return self.profiles_dir / f"{safe}.json"

    def list_profiles(self) -> list[str]:
        return sorted(p.stem for p in self.profiles_dir.glob("*.json"))

    def load_profile(self, name: str) -> ProfileData:
        path = self._path_for(name)
        if not path.exists():
            raise FileNotFoundError(f"Profile '{name}' does not exist.")
        raw = json.loads(path.read_text(encoding="utf-8"))
        profile = ProfileData.from_dict(raw, fallback_name=name)
        errors = profile.validate()
        if errors:
            raise ValueError("Profile validation failed:\n" + "\n".join(errors))
        return profile

    def save_profile(self, profile: ProfileData) -> Path:
        profile.name = self.validate_profile_name(profile.name)
        errors = profile.validate()
        if errors:
            raise ValueError("Cannot save invalid profile:\n" + "\n".join(errors))
        profile.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        path = self._path_for(profile.name)
        path.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")
        return path

    def rename_profile(self, old_name: str, new_name: str) -> Path:
        old_path = self._path_for(old_name)
        if not old_path.exists():
            raise FileNotFoundError(f"Profile '{old_name}' does not exist.")
        new_clean = self.validate_profile_name(new_name)
        new_path = self._path_for(new_clean)
        if new_path.exists() and new_path != old_path:
            raise FileExistsError(f"Profile '{new_clean}' already exists.")
        profile = self.load_profile(old_name)
        profile.name = new_clean
        self.save_profile(profile)
        if new_path != old_path:
            old_path.unlink()
        return new_path

    def delete_profile(self, name: str) -> None:
        path = self._path_for(name)
        if not path.exists():
            raise FileNotFoundError(f"Profile '{name}' does not exist.")
        path.unlink()

    def export_profile(self, name: str, destination: Path) -> Path:
        profile = self.load_profile(name)
        dest = Path(destination)
        dest.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")
        return dest

    def import_profile(self, source: Path, target_name: str | None = None) -> ProfileData:
        src = Path(source)
        raw = json.loads(src.read_text(encoding="utf-8"))
        profile = ProfileData.from_dict(raw, fallback_name=src.stem)
        if target_name:
            profile.name = self.validate_profile_name(target_name)
        else:
            profile.name = self.validate_profile_name(profile.name)
        errors = profile.validate()
        if errors:
            raise ValueError("Imported JSON failed validation:\n" + "\n".join(errors))
        self.save_profile(profile)
        return profile

