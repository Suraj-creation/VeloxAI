from __future__ import annotations

from pathlib import Path
from typing import Iterable

from huggingface_hub import hf_hub_download, list_repo_files, snapshot_download

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = PROJECT_ROOT / "models"

YOLO_REPO = "Ultralytics/YOLOv8"
LP_REPO = "yasirfaizahmed/license-plate-object-detection"


def _first_match(files: Iterable[str], suffix: str) -> str | None:
    for f in files:
        if f.lower().endswith(suffix.lower()):
            return f
    return None


def download_yolov8_base() -> Path:
    # Direct known file for base detector.
    local_path = hf_hub_download(
        repo_id=YOLO_REPO,
        filename="yolov8n.pt",
        local_dir=str(MODELS_DIR / "hf_cache"),
        local_dir_use_symlinks=False,
    )
    out = MODELS_DIR / "twowheeler_yolov8n.pt"
    Path(local_path).replace(out) if not out.exists() else None
    if not out.exists():
        # Fallback copy in case replace was skipped.
        out.write_bytes(Path(local_path).read_bytes())
    return out


def download_lp_model() -> Path:
    files = list_repo_files(LP_REPO)
    pt_file = _first_match(files, ".pt")

    if pt_file:
        local_path = hf_hub_download(
            repo_id=LP_REPO,
            filename=pt_file,
            local_dir=str(MODELS_DIR / "hf_cache"),
            local_dir_use_symlinks=False,
        )
        out = MODELS_DIR / "lp_localiser.pt"
        out.write_bytes(Path(local_path).read_bytes())
        return out

    # Fallback: full snapshot and search manually.
    snap = Path(
        snapshot_download(
            repo_id=LP_REPO,
            local_dir=str(MODELS_DIR / "hf_cache" / "lp_snapshot"),
            local_dir_use_symlinks=False,
        )
    )
    pts = list(snap.rglob("*.pt"))
    if not pts:
        raise RuntimeError("No .pt file found in license plate model repository")
    out = MODELS_DIR / "lp_localiser.pt"
    out.write_bytes(pts[0].read_bytes())
    return out


def main() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print("Downloading pretrained two-wheeler model...")
    yolo_model = download_yolov8_base()
    print(f"Saved: {yolo_model}")

    print("Downloading pretrained license plate model...")
    lp_model = download_lp_model()
    print(f"Saved: {lp_model}")

    print("Model download complete.")


if __name__ == "__main__":
    main()
