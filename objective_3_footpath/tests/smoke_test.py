from __future__ import annotations

from pathlib import Path


def test_runtime_layout() -> None:
    root = Path(__file__).resolve().parents[1]
    expected = [
        root / "main.py",
        root / "requirements_edge.txt",
        root / "scripts" / "install_env.ps1",
        root / "scripts" / "download_models.py",
        root / "scripts" / "init_configs.py",
        root / "config" / "footpath_roi.json",
        root / "config" / "speed_calibration.json",
        root / "config" / "dashboard.json",
    ]
    missing = [str(p) for p in expected if not p.exists()]
    assert not missing, f"Missing required files: {missing}"
