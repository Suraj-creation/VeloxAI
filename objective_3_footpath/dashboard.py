"""
Objective 3 — Live Footpath Enforcement Dashboard
Displays all violations, metrics, trends, and system health in real-time.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent
VIOLATIONS_DIR = PROJECT_ROOT / "violations"
CONFIG_DIR = PROJECT_ROOT / "config"


def load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback


def load_live_metrics() -> dict[str, Any]:
    """Load live metrics from the enforcement app if available."""
    metrics_file = PROJECT_ROOT / ".metrics.json"
    fallback = {
        "timestamp": "",
        "elapsed_ms": 0.0,
        "inference_fps": 0.0,
        "running": False,
        "stats": {},
        "session": {"frame_failures": 0, "reconnects": 0, "live_events": 0},
        "recent_events": [],
    }
    return load_json(metrics_file, fallback)


def scan_violations(max_hours: int = 24) -> list[dict[str, Any]]:
    """Scan violations directory and return list of violation records."""
    violations = []
    cutoff_time = datetime.now() - timedelta(hours=max_hours)

    if not VIOLATIONS_DIR.exists():
        return violations

    for violation_dir in sorted(VIOLATIONS_DIR.iterdir(), reverse=True):
        if not violation_dir.is_dir():
            continue

        metadata_file = violation_dir / "violation_metadata.json"
        if not metadata_file.exists():
            continue

        try:
            with metadata_file.open("r", encoding="utf-8") as f:
                record = json.load(f)

            record_time = datetime.fromisoformat(record.get("timestamp", ""))
            if record_time < cutoff_time:
                continue

            record["_dir_path"] = str(violation_dir)
            violations.append(record)
        except Exception:
            continue

    return violations


def compute_statistics(violations: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregated statistics from violations."""
    if not violations:
        return {
            "total_violations": 0,
            "unique_plates": 0,
            "avg_speed_kmph": 0.0,
            "max_speed_kmph": 0.0,
            "violations_by_class": {},
            "violations_by_hour": {},
            "avg_ocr_confidence": 0.0,
            "plates_by_validation": {"valid": 0, "invalid": 0},
        }

    plates = set()
    speeds = []
    classes = defaultdict(int)
    hours = defaultdict(int)
    ocr_confs = []
    valid_plates = 0
    invalid_plates = 0

    for v in violations:
        plate = v.get("vehicle", {}).get("plate_number", "")
        if plate:
            plates.add(plate)

        speed = v.get("vehicle", {}).get("estimated_speed_kmph", 0.0)
        if speed > 0:
            speeds.append(speed)

        vehicle_class = v.get("vehicle", {}).get("vehicle_class", "unknown")
        classes[vehicle_class] += 1

        timestamp = v.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(timestamp)
            hour_key = ts.strftime("%Y-%m-%d %H:00")
            hours[hour_key] += 1
        except Exception:
            pass

        ocr_conf = v.get("vehicle", {}).get("plate_ocr_confidence", 0.0)
        ocr_confs.append(ocr_conf)

        if v.get("vehicle", {}).get("plate_format_valid", False):
            valid_plates += 1
        else:
            invalid_plates += 1

    return {
        "total_violations": len(violations),
        "unique_plates": len(plates),
        "avg_speed_kmph": round(np.mean(speeds), 2) if speeds else 0.0,
        "max_speed_kmph": round(np.max(speeds), 2) if speeds else 0.0,
        "violations_by_class": dict(sorted(classes.items(), key=lambda x: -x[1])),
        "violations_by_hour": dict(sorted(hours.items())),
        "avg_ocr_confidence": round(np.mean(ocr_confs), 3) if ocr_confs else 0.0,
        "plates_by_validation": {"valid": valid_plates, "invalid": invalid_plates},
    }


def render_dashboard() -> None:
    st.set_page_config(page_title="Objective 3 — Enforcement Dashboard", layout="wide")
    st.title("Objective 3 — Footpath Enforcement Dashboard")
    st.caption("Live monitoring of detection telemetry with persistent analytics from confirmed violations only")

    with st.sidebar:
        st.header("Dashboard Controls")
        refresh_sec = st.slider("Auto Refresh (sec)", min_value=2, max_value=30, value=3, step=1)
        time_range = st.selectbox("Violation Window (hours)", options=[1, 6, 12, 24, 48], index=3)
        table_limit = st.slider("Recent Violations Rows", min_value=10, max_value=200, value=50, step=10)

    # Load configuration
    cam_cfg = load_json(
        CONFIG_DIR / "footpath_roi.json",
        {
            "camera_id": "FP_CAM_001",
            "location_name": "Unknown Location",
            "gps_lat": 0.0,
            "gps_lng": 0.0,
        },
    )

    # Scan violations
    violations = scan_violations(max_hours=time_range)

    # Compute statistics
    stats = compute_statistics(violations)

    # Load live metrics from enforcement app
    live_metrics = load_live_metrics()

    # ============================================================================
    # SECTION 0: LIVE SYSTEM STATUS (if enforcement app is running)
    # ============================================================================
    if live_metrics and live_metrics.get("timestamp"):
        st.subheader("🔴 Live Enforcement App Status")
        live_stats = live_metrics.get("stats", {})
        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            st.metric(
                label="Inference FPS",
                value=f"{live_metrics.get('inference_fps', 0):.1f}",
            )

        with col2:
            st.metric(
                label="Latency (ms)",
                value=f"{live_metrics.get('elapsed_ms', 0):.1f}",
            )

        with col3:
            st.metric(
                label="Detected Objects",
                value=live_stats.get("detected", 0),
            )

        with col4:
            st.metric(
                label="Camera Failures",
                value=live_metrics.get("session", {}).get("frame_failures", 0),
            )

        with col5:
            st.metric(
                label="Reconnects",
                value=live_metrics.get("session", {}).get("reconnects", 0),
            )

        with col6:
            st.metric(
                label="Violations Saved",
                value=live_stats.get("violations_saved", 0),
            )

        st.caption(
            f"Last update: {live_metrics.get('timestamp', 'N/A')} | Mode: {live_stats.get('mode', 'N/A')} | Running: {live_metrics.get('running', False)}"
        )

        class_counts = live_stats.get("class_counts", {})
        if class_counts:
            st.subheader("🎯 Live Frame Class Counts")
            live_class_df = pd.DataFrame(
                [{"Class": key, "Count": value} for key, value in sorted(class_counts.items())]
            )
            st.bar_chart(live_class_df.set_index("Class"), use_container_width=True, color="#339AF0")

        recent_events = live_metrics.get("recent_events", [])
        if recent_events:
            st.subheader("⚡ Live Confirmed Violation Events")
            st.dataframe(pd.DataFrame(recent_events), use_container_width=True, height=220)
    else:
        st.warning("⚠️ Enforcement app not running — no live metrics available. Start the enforcement app to see live data.")

    # ============================================================================
    # SECTION 1: KEY METRICS
    # ============================================================================
    st.subheader("📊 Key Metrics")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="Total Violations",
            value=stats["total_violations"],
            delta=f"Last {time_range}h",
        )

    with col2:
        st.metric(
            label="Unique Plates",
            value=stats["unique_plates"],
        )

    with col3:
        st.metric(
            label="Avg Speed",
            value=f"{stats['avg_speed_kmph']:.1f} km/h",
            delta=f"Max: {stats['max_speed_kmph']:.1f}",
        )

    with col4:
        ocr_rate = (
            (stats["plates_by_validation"]["valid"] / stats["total_violations"] * 100)
            if stats["total_violations"] > 0
            else 0.0
        )
        st.metric(
            label="Valid Plates %",
            value=f"{ocr_rate:.1f}%",
        )

    with col5:
        st.metric(
            label="Avg OCR Confidence",
            value=f"{stats['avg_ocr_confidence']:.2f}",
            delta="0.0–1.0 scale",
        )

    # ============================================================================
    # SECTION 2: VEHICLE CLASS DISTRIBUTION
    # ============================================================================
    st.subheader("🚲 Vehicle Class Distribution")
    col1, col2 = st.columns(2)

    with col1:
        if stats["violations_by_class"]:
            class_df = pd.DataFrame(
                list(stats["violations_by_class"].items()),
                columns=["Vehicle Class", "Count"],
            )
            st.bar_chart(
                class_df.set_index("Vehicle Class"),
                use_container_width=True,
                color="#FF6B6B",
            )
        else:
            st.info("No violations yet.")

    with col2:
        total = (
            stats["plates_by_validation"]["valid"] + stats["plates_by_validation"]["invalid"]
        )
        if total > 0:
            validation_df = pd.DataFrame(
                [
                    {
                        "Status": "Valid",
                        "Count": stats["plates_by_validation"]["valid"],
                    },
                    {
                        "Status": "Invalid",
                        "Count": stats["plates_by_validation"]["invalid"],
                    },
                ],
            )
            st.bar_chart(
                validation_df.set_index("Status"),
                use_container_width=True,
                color=["#51CF66", "#FF6B6B"],
            )
        else:
            st.info("No plate validation data yet.")

    # ============================================================================
    # SECTION 3: VIOLATIONS OVER TIME
    # ============================================================================
    st.subheader("⏱️ Violations Over Time (Hourly)")
    if stats["violations_by_hour"]:
        hour_df = pd.DataFrame(
            [
                {"Hour": k, "Count": v}
                for k, v in sorted(stats["violations_by_hour"].items())
            ]
        )
        st.line_chart(
            hour_df.set_index("Hour"),
            use_container_width=True,
            color="#4ECDC4",
        )
    else:
        st.info("No hourly data yet.")

    # ============================================================================
    # SECTION 4: SYSTEM & LOCATION INFO
    # ============================================================================
    st.subheader("📍 System Information")
    col1, col2 = st.columns(2)

    with col1:
        st.write(f"**Camera ID:** {cam_cfg.get('camera_id', 'N/A')}")
        st.write(f"**Location:** {cam_cfg.get('location_name', 'N/A')}")

    with col2:
        gps_lat = cam_cfg.get("gps_lat", 0.0)
        gps_lng = cam_cfg.get("gps_lng", 0.0)
        st.write(f"**GPS:** {gps_lat:.4f}, {gps_lng:.4f}")
        st.write(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ============================================================================
    # SECTION 5: LIVE VIOLATIONS TABLE
    # ============================================================================
    st.subheader("📋 Recent Violations")

    if violations:
        # Build display dataframe
        display_data = []
        for v in violations[:table_limit]:
            timestamp = v.get("timestamp", "")
            try:
                ts_obj = datetime.fromisoformat(timestamp)
                time_str = ts_obj.strftime("%H:%M:%S")
            except Exception:
                time_str = "N/A"

            display_data.append(
                {
                    "Time": time_str,
                    "Plate": v.get("vehicle", {}).get("plate_number", "N/A"),
                    "Speed (km/h)": v.get("vehicle", {}).get("estimated_speed_kmph", 0),
                    "Class": v.get("vehicle", {}).get("vehicle_class", "unknown"),
                    "OCR Conf": round(
                        v.get("vehicle", {}).get("plate_ocr_confidence", 0.0), 2
                    ),
                    "Valid": "✓" if v.get("vehicle", {}).get("plate_format_valid") else "✗",
                    "Fine (₹)": v.get("fine_amount_inr", 0),
                    "Location": v.get("location", {}).get("location_name", "N/A"),
                    "Violation ID": v.get("violation_id", "")[:8],
                }
            )

        df = pd.DataFrame(display_data)
        st.dataframe(df, use_container_width=True, height=400)
    else:
        st.info("No violations recorded yet.")

    # ============================================================================
    # SECTION 6: VIOLATION DETAILS (EXPANDABLE)
    # ============================================================================
    st.subheader("🔍 Violation Details & Evidence")

    if violations:
        selected_idx = st.selectbox(
            "Select a violation to view details and evidence:",
            range(len(violations)),
            format_func=lambda i: f"{violations[i].get('vehicle', {}).get('plate_number', 'N/A')} @ {violations[i].get('timestamp', 'N/A')[:16]}",
        )

        selected_violation = violations[selected_idx]
        violation_dir = Path(selected_violation["_dir_path"])

        with st.expander("📦 Full Violation Record (JSON)", expanded=False):
            st.json(selected_violation)

        # Display evidence images
        st.write("**Evidence Images:**")
        col1, col2, col3 = st.columns(3)

        evidence_files = {
            "evidence_frame.jpg": "Full Frame with Annotations",
            "plate_crop_raw.jpg": "Plate (Raw)",
            "plate_crop_enhanced.jpg": "Plate (Enhanced)",
        }

        for idx, (file_name, label) in enumerate(evidence_files.items()):
            file_path = violation_dir / file_name
            col = [col1, col2, col3][idx % 3]
            with col:
                if file_path.exists():
                    try:
                        img = Image.open(file_path)
                        st.image(img, caption=label, use_container_width=True)
                    except Exception:
                        st.warning(f"Unable to load {label}")
                else:
                    st.info(f"{label} not available")

        # Display violation metadata in structured format
        st.write("**Violation Details:**")
        col1, col2 = st.columns(2)

        with col1:
            st.write(
                f"**Violation ID:** `{selected_violation.get('violation_id', 'N/A')}`"
            )
            st.write(
                f"**Timestamp:** {selected_violation.get('timestamp', 'N/A')}"
            )
            st.write(
                f"**Plate Number:** {selected_violation.get('vehicle', {}).get('plate_number', 'N/A')}"
            )
            st.write(
                f"**Plate OCR Confidence:** {selected_violation.get('vehicle', {}).get('plate_ocr_confidence', 0.0):.3f}"
            )
            st.write(
                f"**Plate Format Valid:** {selected_violation.get('vehicle', {}).get('plate_format_valid', False)}"
            )

        with col2:
            st.write(
                f"**Vehicle Class:** {selected_violation.get('vehicle', {}).get('vehicle_class', 'N/A')}"
            )
            st.write(
                f"**Estimated Speed:** {selected_violation.get('vehicle', {}).get('estimated_speed_kmph', 0.0):.1f} km/h"
            )
            st.write(
                f"**Track ID:** {selected_violation.get('vehicle', {}).get('track_id', 'N/A')}"
            )
            st.write(
                f"**Fine Amount:** ₹{selected_violation.get('fine_amount_inr', 0)}"
            )

        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Camera ID:** {selected_violation.get('location', {}).get('camera_id', 'N/A')}")
            st.write(f"**Location Name:** {selected_violation.get('location', {}).get('location_name', 'N/A')}")
        with col2:
            gps = selected_violation.get("location", {})
            st.write(f"**GPS:** {gps.get('gps_lat', 0):.4f}, {gps.get('gps_lng', 0):.4f}")
            st.write(f"**Violation Type:** {selected_violation.get('violation_type', 'N/A')}")

    else:
        st.info("No violations to display.")

    # ============================================================================
    # SECTION 7: AUTO-REFRESH
    # ============================================================================
    st.markdown("---")
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🔄 Refresh Now"):
            st.rerun()
    with col2:
        st.caption(
            f"Dashboard auto-refreshes every {refresh_sec} seconds. Click 'Refresh Now' for immediate update."
        )

    time.sleep(refresh_sec)
    st.rerun()


if __name__ == "__main__":
    render_dashboard()
