"""Unit tests for ConfigurationService and CalibrationService."""

from pathlib import Path

from models.sensor_data import IMUData
from services.calibration_service import CalibrationService
from services.configuration_service import ConfigurationService, ProfileData


def test_configuration_profile_crud(tmp_path: Path) -> None:
    svc = ConfigurationService(tmp_path)
    assert "Default Quad-X" in svc.list_profiles()

    prof = ProfileData(name="Indoor Tune", notes="Soft P gains")
    svc.save_profile(prof)
    assert "Indoor Tune" in svc.list_profiles()

    loaded = svc.load_profile("Indoor Tune")
    assert loaded.notes == "Soft P gains"

    svc.rename_profile("Indoor Tune", "Outdoor Tune")
    assert "Outdoor Tune" in svc.list_profiles()
    assert "Indoor Tune" not in svc.list_profiles()

    export_file = tmp_path / "exported.json"
    svc.export_profile("Outdoor Tune", export_file)
    assert export_file.exists()

    imported = svc.import_profile(export_file, target_name="Imported Tune")
    assert imported.name == "Imported Tune"

    svc.delete_profile("Outdoor Tune")
    assert "Outdoor Tune" not in svc.list_profiles()


def test_calibration_stationary_check() -> None:
    cal = CalibrationService(window_size=10)
    ok, _ = cal.is_stationary()
    assert ok is False

    for _ in range(10):
        cal.push_sample(IMUData(ax=0.01, ay=-0.01, az=1.0, gx=0.2, gy=-0.1, gz=0.1, mpu_connected=True))
    ok, _ = cal.is_stationary()
    assert ok is True

    cal.push_sample(IMUData(ax=0.01, ay=-0.01, az=1.0, gx=12.0, gy=0.0, gz=0.0, mpu_connected=True))
    ok, msg = cal.is_stationary()
    assert ok is False
    assert "Motion detected" in msg

