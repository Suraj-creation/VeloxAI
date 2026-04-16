from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from paddleocr import PaddleOCR
from ultralytics import YOLO

from backend_sync import EdgeSyncClient

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PROJECT_ROOT / "config"
MODELS_DIR = PROJECT_ROOT / "models"
FRONTEND_LAB_CONFIG = CONFIG_DIR / "frontend_camera_lab.json"
METRICS_FILE = PROJECT_ROOT / ".metrics.json"
PREVIEW_FILE = PROJECT_ROOT / ".preview_annotated.jpg"

GENERAL_MODEL_PATH = MODELS_DIR / "hf_cache" / "yolov8n.pt"
ENFORCEMENT_MODEL_PATH = MODELS_DIR / "twowheeler_yolov8n.pt"
LP_MODEL_PATH = MODELS_DIR / "lp_localiser.pt"

VEHICLE_CLASSES = {"motorcycle", "bicycle", "car", "bus", "truck", "scooter"}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_json_safe(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    try:
        with path.open("r", encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else fallback
    except Exception:
        return fallback


def validate_plate(text: str) -> bool:
    pattern = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$")
    bh_pattern = re.compile(r"^[0-9]{2}BH[0-9]{4}[A-Z]{2}$")
    return bool(pattern.match(text) or bh_pattern.match(text))


def enhance_plate_cpu(plate_img: np.ndarray) -> np.ndarray:
    target_w = max(400, plate_img.shape[1] * 3)
    scale = target_w / max(plate_img.shape[1], 1)
    new_h = max(32, int(plate_img.shape[0] * scale))
    up = cv2.resize(plate_img, (target_w, new_h), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
    eq = clahe.apply(gray)
    blur = cv2.GaussianBlur(eq, (0, 0), 1.5)
    sharp = cv2.addWeighted(eq, 1.8, blur, -0.8, 0)
    denoised = cv2.bilateralFilter(sharp, 5, 40, 40)
    return cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)


def clean_plate_text(raw: str) -> str:
    text = raw.upper().replace(" ", "").replace("-", "").replace(".", "")
    return re.sub(r"[^A-Z0-9]", "", text)


def export_metrics(stats: dict[str, Any], elapsed_ms: float, running: bool = True) -> None:
    elapsed = round(float(elapsed_ms), 1)
    inference_fps = round(1000.0 / float(elapsed_ms), 1) if float(elapsed_ms) > 0.0 else 0.0

    payload = {
        "timestamp": datetime.now().isoformat(),
        "elapsed_ms": elapsed,
        "inference_fps": inference_fps,
        "running": bool(running),
        "stats": stats,
        "session": {
            "frame_failures": int(stats.get("frame_failures", 0)),
            "reconnects": int(stats.get("reconnects", 0)),
            "live_events": int(stats.get("violations_saved", 0)),
        },
        "recent_events": [],
    }

    temp_file = METRICS_FILE.with_suffix(".json.tmp")
    try:
        with temp_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f)
        temp_file.replace(METRICS_FILE)
    except Exception:
        pass


def export_preview_frame(frame: np.ndarray) -> None:
    temp_file = PREVIEW_FILE.with_suffix(".tmp.jpg")
    try:
        ok = cv2.imwrite(str(temp_file), frame)
        if ok:
            temp_file.replace(PREVIEW_FILE)
    except Exception:
        pass


def select_runtime_mode(lab_cfg: dict[str, Any]) -> str:
    enable_plate = bool(lab_cfg.get("enablePlatePipeline", True))
    return "Footpath Enforcement" if enable_plate else "General Detection"


def select_source_from_lab(lab_cfg: dict[str, Any], fallback: str | int) -> str | int:
    source_mode = str(lab_cfg.get("sourceMode", "device")).strip().lower()
    source_value = str(lab_cfg.get("sourceValue", "0")).strip()

    if source_mode == "rtsp":
        return source_value or fallback

    if source_value.isdigit():
        return int(source_value)

    return fallback


def open_capture(source: str | int, width: int, height: int) -> cv2.VideoCapture:
    # Prefer DirectShow for USB webcams on Windows, then fall back to MSMF/default.
    backends: list[int | None] = [None]
    if isinstance(source, int):
        cap_dshow = getattr(cv2, "CAP_DSHOW", None)
        cap_msmf = getattr(cv2, "CAP_MSMF", None)
        backends = [cap_dshow, cap_msmf, None]

    for backend in backends:
        cap = cv2.VideoCapture(source, backend) if backend is not None else cv2.VideoCapture(source)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))
            return cap
        cap.release()

    return cv2.VideoCapture(source)


def draw_box(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int, label: str, color: tuple[int, int, int]) -> None:
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    cv2.putText(frame, label, (x1, max(18, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)


def frame_signal_metrics(frame: np.ndarray) -> tuple[float, float]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray)), float(np.std(gray))


def run_general_detection(frame: np.ndarray, model: YOLO, conf: float) -> tuple[np.ndarray, dict[str, Any]]:
    annotated = frame.copy()
    result = model(annotated, conf=conf, verbose=False)[0]

    class_counts: dict[str, int] = {}
    total = 0

    if result.boxes is not None and len(result.boxes) > 0:
        boxes = result.boxes.xyxy.cpu().numpy().astype(int)
        classes = result.boxes.cls.cpu().numpy().astype(int)
        scores = result.boxes.conf.cpu().numpy()

        for bbox, cls_id, score in zip(boxes, classes, scores):
            x1, y1, x2, y2 = bbox.tolist()
            name = result.names.get(cls_id, str(cls_id))
            class_key = name.lower()
            class_counts[class_key] = class_counts.get(class_key, 0) + 1
            total += 1
            draw_box(annotated, x1, y1, x2, y2, f"{name} {score:.2f}", (0, 200, 255))

    stats = {
        "mode": "General Detection",
        "detected": total,
        "moving_hits": 0,
        "plates_read": 0,
        "violations_saved": 0,
        "class_counts": class_counts,
    }

    return annotated, stats


def run_smoke(video_source: str | int = 0, max_frames: int = 60) -> None:
    speed_cfg = load_json(CONFIG_DIR / "speed_calibration.json")
    ppm = float(speed_cfg.get("pixels_per_metre", 47.0))
    fps_cfg = float(speed_cfg.get("camera_fps", 15.0))

    lab_cfg = load_json_safe(FRONTEND_LAB_CONFIG, {})
    mode = select_runtime_mode(lab_cfg)
    conf_threshold = float(lab_cfg.get("detectionConfidence", 0.35) or 0.35)
    speed_threshold = float(lab_cfg.get("speedThresholdKmph", 5.0) or 5.0)
    cooldown_sec = int(lab_cfg.get("cooldownSec", 60) or 60)
    min_ocr_conf = float(lab_cfg.get("minOcrConfidence", 0.65) or 0.65)
    target_width = int(lab_cfg.get("previewWidth", 1280) or 1280)
    target_height = int(lab_cfg.get("previewHeight", 720) or 720)
    target_fps = int(lab_cfg.get("targetFps", 12) or 12)

    detector_path = ENFORCEMENT_MODEL_PATH if mode == "Footpath Enforcement" else GENERAL_MODEL_PATH
    if not detector_path.exists():
        raise RuntimeError(f"Model not found: {detector_path}")

    detector_model = YOLO(str(detector_path))
    lp_model = YOLO(str(LP_MODEL_PATH)) if mode == "Footpath Enforcement" and LP_MODEL_PATH.exists() else None
    ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)

    track_hist: dict[int, deque[tuple[int, int]]] = defaultdict(lambda: deque(maxlen=10))
    last_violation_by_track: dict[int, float] = {}

    selected_source = select_source_from_lab(lab_cfg, video_source)
    cap = open_capture(selected_source, target_width, target_height)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open source: {selected_source}")

    sync_client = EdgeSyncClient(base_url="http://localhost:8000", api_key="dev-key")
    camera_id = str(lab_cfg.get("cameraId", f"cam-{selected_source}" if isinstance(selected_source, int) else "cam-stream"))
    config_poll_interval_frames = 10

    print("Starting smoke run...")
    frame_count = 0
    reconnects = 0
    frame_failures = 0

    frame_limit = max_frames

    while frame_limit <= 0 or frame_count < frame_limit:
        if frame_count % config_poll_interval_frames == 0:
            latest_cfg = load_json_safe(FRONTEND_LAB_CONFIG, {})
            latest_mode = select_runtime_mode(latest_cfg)
            latest_conf = float(latest_cfg.get("detectionConfidence", 0.35) or 0.35)
            latest_speed = float(latest_cfg.get("speedThresholdKmph", 5.0) or 5.0)
            latest_cooldown = int(latest_cfg.get("cooldownSec", 60) or 60)
            latest_min_ocr = float(latest_cfg.get("minOcrConfidence", 0.65) or 0.65)
            latest_width = int(latest_cfg.get("previewWidth", 1280) or 1280)
            latest_height = int(latest_cfg.get("previewHeight", 720) or 720)
            latest_fps = int(latest_cfg.get("targetFps", 12) or 12)
            latest_source = select_source_from_lab(latest_cfg, selected_source)

            mode_changed = latest_mode != mode
            source_changed = latest_source != selected_source
            shape_changed = latest_width != target_width or latest_height != target_height

            lab_cfg = latest_cfg
            mode = latest_mode
            conf_threshold = latest_conf
            speed_threshold = latest_speed
            cooldown_sec = latest_cooldown
            min_ocr_conf = latest_min_ocr
            target_width = latest_width
            target_height = latest_height
            target_fps = latest_fps
            camera_id = str(lab_cfg.get("cameraId", f"cam-{latest_source}" if isinstance(latest_source, int) else "cam-stream"))

            if mode_changed:
                detector_path = ENFORCEMENT_MODEL_PATH if mode == "Footpath Enforcement" else GENERAL_MODEL_PATH
                if not detector_path.exists():
                    raise RuntimeError(f"Model not found: {detector_path}")
                detector_model = YOLO(str(detector_path))
                lp_model = YOLO(str(LP_MODEL_PATH)) if mode == "Footpath Enforcement" and LP_MODEL_PATH.exists() else None
                track_hist.clear()
                last_violation_by_track.clear()

            if source_changed or shape_changed:
                selected_source = latest_source
                cap.release()
                cap = open_capture(selected_source, target_width, target_height)
                reconnects += 1

                if not cap.isOpened():
                    stats = {
                        "mode": mode,
                        "status": "waiting_source",
                        "detected": 0,
                        "moving_hits": 0,
                        "plates_read": 0,
                        "violations_saved": 0,
                        "class_counts": {},
                        "frame_failures": frame_failures,
                        "reconnects": reconnects,
                        "source_camera": str(selected_source),
                    }
                    export_metrics(stats, 0.0, running=True)
                    time.sleep(0.25)
                    continue

        ok, frame = cap.read()
        if not ok:
            frame_failures += 1
            if frame_failures >= 8:
                reconnects += 1
                cap.release()
                time.sleep(0.25)
                cap = open_capture(selected_source, target_width, target_height)
                frame_failures = 0

            stats = {
                "mode": mode,
                "status": "waiting_frame",
                "detected": 0,
                "moving_hits": 0,
                "plates_read": 0,
                "violations_saved": 0,
                "class_counts": {},
                "frame_failures": frame_failures,
                "reconnects": reconnects,
                "source_camera": str(selected_source),
            }
            export_metrics(stats, 0.0, running=True)
            time.sleep(0.08)
            continue

        frame_failures = 0

        signal_mean_luma, signal_std_luma = frame_signal_metrics(frame)
        signal_flat = signal_std_luma < 4.0 or signal_mean_luma < 5.0 or signal_mean_luma > 250.0
        if signal_flat:
            annotated = frame.copy()
            cv2.putText(
                annotated,
                "Camera signal looks flat/overexposed.",
                (24, 34),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (0, 0, 255),
                2,
            )
            cv2.putText(
                annotated,
                "Check privacy shutter, lens cover, lighting, and camera selection.",
                (24, 64),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255),
                2,
            )
            export_preview_frame(annotated)
            export_metrics(
                {
                    "mode": mode,
                    "status": "signal_flat",
                    "detected": 0,
                    "moving_hits": 0,
                    "plates_read": 0,
                    "violations_saved": 0,
                    "reconnects": int(reconnects),
                    "camera_failures": int(frame_failures),
                    "frame_failures": int(frame_failures),
                    "source_camera": str(selected_source),
                    "signal_mean_luma": round(signal_mean_luma, 2),
                    "signal_std_luma": round(signal_std_luma, 2),
                    "class_counts": {},
                },
                0.0,
                running=True,
            )
            time.sleep(max(0.05, 1.0 / max(target_fps, 1)))
            continue

        frame_count += 1
        t0 = time.time()

        violations_saved = 0
        moving_hits = 0
        plates_read = 0
        detected = 0
        class_counts: dict[str, int] = {}
        annotated = frame.copy()

        if mode == "General Detection":
            annotated, run_stats = run_general_detection(frame, detector_model, conf_threshold)
            detected = int(run_stats.get("detected", 0))
            class_counts = dict(run_stats.get("class_counts", {}))
        else:
            results = detector_model.track(frame, persist=True, tracker="bytetrack.yaml", conf=conf_threshold, verbose=False)
            if results and results[0].boxes is not None and len(results[0].boxes) > 0:
                boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
                classes = results[0].boxes.cls.cpu().numpy().astype(int)
                scores = results[0].boxes.conf.cpu().numpy()
                ids_tensor = results[0].boxes.id
                ids = ids_tensor.cpu().numpy().astype(int) if ids_tensor is not None else np.arange(len(boxes))
                names = results[0].names

                for bbox, cls_id, score, track_id in zip(boxes, classes, scores, ids):
                    x1, y1, x2, y2 = bbox.tolist()
                    name = names.get(cls_id, str(cls_id))
                    class_key = str(name).lower()
                    class_counts[class_key] = class_counts.get(class_key, 0) + 1
                    detected += 1

                    center = ((x1 + x2) // 2, y2)
                    speed = 0.0
                    if class_key in VEHICLE_CLASSES:
                        track_hist[int(track_id)].append(center)
                        if len(track_hist[int(track_id)]) >= 3:
                            p1 = np.array(track_hist[int(track_id)][-2], dtype=np.float32)
                            p2 = np.array(track_hist[int(track_id)][-1], dtype=np.float32)
                            speed = float(np.linalg.norm(p2 - p1) / max(ppm, 1e-6) * fps_cfg * 3.6)
                            if speed >= speed_threshold:
                                moving_hits += 1

                    draw_box(annotated, x1, y1, x2, y2, f"id:{track_id} {name} {score:.2f} {speed:.1f}km/h", (0, 200, 255))

                    if speed < speed_threshold or lp_model is None:
                        continue

                    crop = frame[max(0, y1):max(1, y2), max(0, x1):max(1, x2)]
                    if crop.size == 0:
                        continue

                    lp_results = lp_model(crop, conf=0.3, verbose=False)
                    if not lp_results or len(lp_results[0].boxes) == 0:
                        continue

                    lp_boxes = lp_results[0].boxes.xyxy.cpu().numpy().astype(int)
                    lp_scores = lp_results[0].boxes.conf.cpu().numpy() if lp_results[0].boxes.conf is not None else np.ones(len(lp_boxes))
                    best_idx = int(np.argmax(lp_scores))
                    lx1, ly1, lx2, ly2 = lp_boxes[best_idx].tolist()
                    plate = crop[max(0, ly1):max(1, ly2), max(0, lx1):max(1, lx2)]
                    if plate.size == 0:
                        continue

                    plates_read += 1
                    enhanced = enhance_plate_cpu(plate)
                    text_result = ocr.ocr(enhanced, cls=True)
                    if not text_result or not text_result[0]:
                        continue

                    raw = "".join([line[1][0] for line in text_result[0]])
                    cleaned = clean_plate_text(raw)
                    is_valid = validate_plate(cleaned)
                    plate_conf = float(np.mean([line[1][1] for line in text_result[0]]))

                    draw_box(annotated, x1 + lx1, y1 + ly1, x1 + lx2, y1 + ly2, f"plate:{cleaned or 'N/A'} {plate_conf:.2f}", (0, 255, 0))

                    now = time.time()
                    last_ts = float(last_violation_by_track.get(int(track_id), 0.0))
                    if now - last_ts < cooldown_sec:
                        continue

                    if not is_valid or plate_conf < min_ocr_conf:
                        continue

                    last_violation_by_track[int(track_id)] = now
                    violations_saved += 1

                    violation_id = f"v-{int(now)}-{track_id}"
                    timestamp = datetime.now(timezone.utc).isoformat()
                    payload = {
                        "violation_id": violation_id,
                        "timestamp": timestamp,
                        "location": {
                            "camera_id": camera_id,
                            "location_name": str(lab_cfg.get("locationName", "Headless Runtime")),
                        },
                        "vehicle": {
                            "plate_number": cleaned,
                            "plate_ocr_confidence": round(plate_conf, 3),
                            "plate_format_valid": is_valid,
                            "vehicle_class": class_key,
                            "estimated_speed_kmph": round(speed, 2),
                            "track_id": int(track_id),
                        },
                    }
                    sync_client.send_violation(payload)
                    sync_client.upload_evidence(violation_id, b"dummy", b"dummy")

        latency_ms = (time.time() - t0) * 1000
        export_preview_frame(annotated)

        run_stats = {
            "mode": mode,
            "status": "processing",
            "detected": int(detected),
            "moving_hits": int(moving_hits),
            "plates_read": int(plates_read),
            "violations_saved": int(violations_saved),
            "reconnects": int(reconnects),
            "camera_failures": int(frame_failures),
            "frame_failures": int(frame_failures),
            "source_camera": str(selected_source),
            "signal_mean_luma": round(signal_mean_luma, 2),
            "signal_std_luma": round(signal_std_luma, 2),
            "class_counts": class_counts,
        }
        export_metrics(run_stats, latency_ms, running=True)

        if frame_count % 10 == 0:
            print(f"frame={frame_count} latency_ms={latency_ms:.1f}")
            actual_fps = 1000.0 / latency_ms if latency_ms > 0 else fps_cfg
            sync_client.send_telemetry(camera_id, actual_fps, latency_ms)

        sleep_for = max(0.0, (1.0 / max(target_fps, 1)) - (latency_ms / 1000.0))
        if sleep_for > 0:
            time.sleep(sleep_for)

    cap.release()
    export_metrics(
        {
            "mode": mode,
            "status": "stopped",
            "detected": 0,
            "moving_hits": 0,
            "plates_read": 0,
            "violations_saved": 0,
            "class_counts": {},
            "frame_failures": 0,
            "reconnects": reconnects,
            "source_camera": str(selected_source),
        },
        0.0,
        running=False,
    )
    print("Smoke run complete.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="auto", help="Camera index, rtsp URL, file path, or 'auto' from frontend config")
    parser.add_argument("--frames", type=int, default=0, help="Max frames for smoke run (0 means run continuously)")
    return parser.parse_args()


def normalize_source(source: str) -> str | int:
    if source == "auto":
        cfg = load_json_safe(FRONTEND_LAB_CONFIG, {})
        return select_source_from_lab(cfg, 0)
    if source.isdigit():
        return int(source)
    return source


if __name__ == "__main__":
    args = parse_args()
    run_smoke(video_source=normalize_source(args.source), max_frames=args.frames)
