from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".m4v"}


def find_clips(clips_dir: Path) -> list[Path]:
    clips = [p for p in clips_dir.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS]
    clips.sort()
    return clips


def run_clip(project_root: Path, clip: Path, frames_per_clip: int) -> tuple[bool, float, str]:
    cmd = [
        str(project_root / ".venv" / "Scripts" / "python.exe"),
        str(project_root / "main.py"),
        "--source",
        str(clip),
        "--frames",
        str(frames_per_clip),
    ]

    start = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - start

    ok = proc.returncode == 0
    tail = (proc.stdout + "\n" + proc.stderr).strip()[-2000:]
    return ok, elapsed, tail


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run objective_3 runtime over up to 180 clips.")
    parser.add_argument("--clips-dir", required=True, help="Directory containing evaluation clips")
    parser.add_argument("--max-clips", type=int, default=180)
    parser.add_argument("--frames-per-clip", type=int, default=120)
    parser.add_argument("--report-json", default="logs/eval_180_report.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    clips_dir = Path(args.clips_dir)

    if not clips_dir.exists():
        raise FileNotFoundError(f"clips-dir does not exist: {clips_dir}")

    clips = find_clips(clips_dir)
    if not clips:
        raise RuntimeError(f"No video clips found in: {clips_dir}")

    selected = clips[: args.max_clips]

    results: list[dict] = []
    failures = 0

    print(f"Found {len(clips)} clips, evaluating {len(selected)} clip(s)...")

    for idx, clip in enumerate(selected, start=1):
        ok, elapsed, tail = run_clip(project_root, clip, args.frames_per_clip)
        if not ok:
            failures += 1
        print(f"[{idx}/{len(selected)}] {'OK' if ok else 'FAIL'} {clip.name} ({elapsed:.1f}s)")
        results.append(
            {
                "index": idx,
                "clip": str(clip),
                "ok": ok,
                "elapsed_sec": round(elapsed, 3),
                "output_tail": tail,
            }
        )

    report = {
        "total_found": len(clips),
        "total_evaluated": len(selected),
        "failures": failures,
        "successes": len(selected) - failures,
        "success_rate": round((len(selected) - failures) / len(selected), 4),
        "frames_per_clip": args.frames_per_clip,
        "generated_at_epoch": int(time.time()),
        "results": results,
    }

    report_path = project_root / args.report_json
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Report written: {report_path}")

    # Non-zero if any clip failed.
    if failures:
        sys.exit(2)


if __name__ == "__main__":
    main()
