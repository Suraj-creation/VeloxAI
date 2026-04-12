from __future__ import annotations

import base64
import json
import re
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import streamlit as st
from ultralytics import YOLO

try:
    from paddleocr import PaddleOCR

    PADDLEOCR_AVAILABLE = True
except Exception:
    PaddleOCR = None
    PADDLEOCR_AVAILABLE = False

try:
    import paho.mqtt.client as mqtt

    PAHO_AVAILABLE = True
except Exception:
    mqtt = None
    PAHO_AVAILABLE = False

PROJECT_ROOT = Path(__file__).resolve().parent
MODELS_DIR = PROJECT_ROOT / "models"
CONFIG_DIR = PROJECT_ROOT / "config"
VIOLATIONS_DIR = PROJECT_ROOT / "violations"
FRONTEND_LAB_CONFIG = CONFIG_DIR / "frontend_camera_lab.json"

TWO_WHEELER_MODEL = MODELS_DIR / "twowheeler_yolov8n.pt"
LP_MODEL = MODELS_DIR / "lp_localiser.pt"
GENERAL_MODEL = MODELS_DIR / "hf_cache" / "yolov8n.pt"

VEHICLE_CLASSES = {"motorcycle", "bicycle", "car", "bus", "truck", "scooter"}
INDIAN_PLATE_PATTERN = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$")
BH_PATTERN = re.compile(r"^[0-9]{2}BH[0-9]{4}[A-Z]{2}$")


def load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def clean_plate_text(raw: str) -> str:
    text = raw.upper().replace(" ", "").replace("-", "").replace(".", "")
    text = re.sub(r"[^A-Z0-9]", "", text)
    if len(text) >= 10:
        chars = list(text)
        letter_to_digit = {"O": "0", "I": "1", "Z": "2", "S": "5", "B": "8", "G": "6"}
        digit_to_letter = {"0": "O", "1": "I", "5": "S", "8": "B", "6": "G"}
        for pos in [2, 3, 6, 7, 8, 9]:
            if pos < len(chars):
                chars[pos] = letter_to_digit.get(chars[pos], chars[pos])
        for pos in [0, 1, 4, 5]:
            if pos < len(chars):
                chars[pos] = digit_to_letter.get(chars[pos], chars[pos])
        text = "".join(chars)
    return text


def validate_plate(text: str) -> bool:
    return bool(INDIAN_PLATE_PATTERN.match(text) or BH_PATTERN.match(text))


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


def ocr_with_voting(plate_img: np.ndarray, ocr: Any) -> dict[str, Any]:
    augmentations = [
        lambda x: x,
        lambda x: cv2.convertScaleAbs(x, alpha=1.1, beta=10),
        lambda x: cv2.convertScaleAbs(x, alpha=0.9, beta=-10),
    ]

    best = {"raw_text": "", "cleaned_text": "", "confidence": 0.0, "is_valid": False}
    for aug in augmentations:
        test_img = aug(plate_img)
        result = ocr.ocr(test_img, cls=True)
        if not result or not result[0]:
            continue
        raw_text = "".join([line[1][0] for line in result[0]])
        conf = float(np.mean([line[1][1] for line in result[0]]))
        cleaned = clean_plate_text(raw_text)
        valid = validate_plate(cleaned)
        candidate = {
            "raw_text": raw_text,
            "cleaned_text": cleaned,
            "confidence": conf,
            "is_valid": valid,
        }
        if valid and conf >= best["confidence"]:
            best = candidate
        elif not best["is_valid"] and conf >= best["confidence"]:
            best = candidate

    return best


def bbox_bottom_center(bbox: np.ndarray) -> tuple[int, int]:
    x1, y1, x2, y2 = [int(v) for v in bbox]
    return (int((x1 + x2) / 2), int(y2))


def compute_speed_kmph(points: deque[tuple[int, int]], pixels_per_metre: float, fps: float) -> float:
    if len(points) < 3:
        return 0.0
    recent = list(points)[-3:]
    total = 0.0
    for i in range(1, len(recent)):
        dx = recent[i][0] - recent[i - 1][0]
        dy = recent[i][1] - recent[i - 1][1]
        total += float(np.hypot(dx, dy))
    avg_px_per_frame = total / (len(recent) - 1)
    mps = (avg_px_per_frame / max(pixels_per_metre, 1e-6)) * fps
    return mps * 3.6


def ensure_state() -> None:
    if "running" not in st.session_state:
        st.session_state.running = False
    if "frame_failures" not in st.session_state:
        st.session_state.frame_failures = 0
    if "reconnects" not in st.session_state:
        st.session_state.reconnects = 0
    if "track_history" not in st.session_state:
        st.session_state.track_history = defaultdict(lambda: deque(maxlen=10))
    if "last_violation_by_track" not in st.session_state:
        st.session_state.last_violation_by_track = {}
    if "events" not in st.session_state:
        st.session_state.events = []
    if "camera_stream" not in st.session_state:
        st.session_state.camera_stream = None
    if "latest_frame_at" not in st.session_state:
        st.session_state.latest_frame_at = 0.0
    if "preview_export_at" not in st.session_state:
        st.session_state.preview_export_at = 0.0


def release_camera() -> None:
    stream = st.session_state.get("camera_stream")
    if stream is not None:
        stream.stop()
    st.session_state.camera_stream = None


class CameraStream:
    def __init__(self, camera_index: int, width: int, height: int) -> None:
        self.camera_index = int(camera_index)
        self.width = int(width)
        self.height = int(height)
        self._cap: cv2.VideoCapture | None = None
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _open(self) -> cv2.VideoCapture | None:
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            return None
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(self.width))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self.height))
        return cap

    def _reader(self) -> None:
        while not self._stopped.is_set():
            if self._cap is None or not self._cap.isOpened():
                self._cap = self._open()
                if self._cap is None:
                    time.sleep(0.5)
                    continue

            ok, frame = self._cap.read()
            if ok and frame is not None and frame.size > 0:
                with self._lock:
                    self._frame = frame.copy()
                continue

            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
            time.sleep(0.1)

        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def get_frame(self) -> np.ndarray | None:
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def stop(self) -> None:
        self._stopped.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)


def read_frame_with_recovery(camera_index: int, width: int, height: int, max_failures: int) -> tuple[np.ndarray | None, str]:
    stream = st.session_state.camera_stream
    if stream is None:
        stream = CameraStream(camera_index, width, height)
        st.session_state.camera_stream = stream

    frame = stream.get_frame()
    if frame is not None and frame.size > 0:
        st.session_state.frame_failures = 0
        st.session_state.latest_frame_at = time.time()
        return frame, "ok"

    st.session_state.frame_failures += 1
    if st.session_state.frame_failures >= max_failures:
        st.session_state.reconnects += 1
        st.session_state.frame_failures = 0
        return None, "retry"

    return None, "retry"


@st.cache_resource(show_spinner=True)
def load_models(detector_model_path: str, use_plate_pipeline: bool):
    detector = YOLO(detector_model_path)
    lp_model = YOLO(str(LP_MODEL)) if use_plate_pipeline and LP_MODEL.exists() else None
    ocr = (
        PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        if use_plate_pipeline and PADDLEOCR_AVAILABLE
        else None
    )
    return detector, lp_model, ocr


def save_violation(
    frame: np.ndarray,
    plate_raw: np.ndarray | None,
    plate_enhanced: np.ndarray | None,
    metadata: dict[str, Any],
) -> Path:
    VIOLATIONS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    plate_token = metadata["vehicle"]["plate_number"] or "UNKNOWN"
    folder = VIOLATIONS_DIR / f"{ts}_{plate_token}_{metadata['violation_id'][:8]}"
    folder.mkdir(parents=True, exist_ok=True)

    frame_path = folder / "evidence_frame.jpg"
    cv2.imwrite(str(frame_path), frame)

    raw_path = folder / "plate_crop_raw.jpg"
    enhanced_path = folder / "plate_crop_enhanced.jpg"
    if plate_raw is not None and plate_raw.size > 0:
        cv2.imwrite(str(raw_path), plate_raw)
    if plate_enhanced is not None and plate_enhanced.size > 0:
        cv2.imwrite(str(enhanced_path), plate_enhanced)

    thumb_path = folder / "thumbnail.jpg"
    thumb = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(thumb_path), thumb)

    metadata["evidence"] = {
        "full_frame": str(frame_path),
        "plate_crop_raw": str(raw_path),
        "plate_crop_enhanced": str(enhanced_path),
        "thumbnail": str(thumb_path),
    }

    with (folder / "violation_metadata.json").open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return folder


def render_frame(slot: Any, frame: np.ndarray) -> None:
    ok, buffer = cv2.imencode(".jpg", frame)
    if not ok:
        slot.warning("Unable to render camera frame.")
        return

    encoded = base64.b64encode(buffer.tobytes()).decode("ascii")
    slot.markdown(
        f"<img src=\"data:image/jpeg;base64,{encoded}\" style=\"width:100%; height:auto; border-radius:12px;\" />",
        unsafe_allow_html=True,
    )


def export_metrics(stats: dict[str, Any], elapsed_ms: float) -> None:
    """Export live metrics to a JSON file for dashboard consumption."""
    metrics_file = PROJECT_ROOT / ".metrics.json"
    temp_file = PROJECT_ROOT / ".metrics.json.tmp"
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "elapsed_ms": round(elapsed_ms, 1),
        "inference_fps": round(1000.0 / max(elapsed_ms, 1e-6), 1),
        "running": bool(st.session_state.running),
        "stats": stats,
        "session": {
            "frame_failures": int(st.session_state.frame_failures),
            "reconnects": int(st.session_state.reconnects),
            "live_events": len(st.session_state.events),
        },
        "recent_events": st.session_state.events[:10],
    }
    try:
        with temp_file.open("w", encoding="utf-8") as f:
            json.dump(metrics, f)
        temp_file.replace(metrics_file)
    except Exception:
        pass


def export_preview_frame(frame: np.ndarray, min_interval_sec: float = 0.4) -> None:
    now = time.time()
    last = float(st.session_state.get("preview_export_at", 0.0))
    if now - last < min_interval_sec:
        return

    frame_path = PROJECT_ROOT / ".preview_annotated.jpg"
    temp_path = PROJECT_ROOT / ".preview_annotated.tmp.jpg"
    try:
        ok = cv2.imwrite(str(temp_path), frame)
        if ok:
            temp_path.replace(frame_path)
            st.session_state.preview_export_at = now
    except Exception:
        pass


def push_mqtt_if_enabled(record: dict[str, Any], mqtt_cfg: dict[str, Any], enabled: bool) -> bool:
    if not enabled or not PAHO_AVAILABLE:
        return False
    try:
        client = mqtt.Client()
        client.connect(str(mqtt_cfg.get("mqtt_host", "localhost")), int(mqtt_cfg.get("mqtt_port", 1883)), 5)
        payload = json.dumps(
            {
                "violation_id": record["violation_id"],
                "timestamp": record["timestamp"],
                "plate": record["vehicle"]["plate_number"],
                "speed_kmph": record["vehicle"]["estimated_speed_kmph"],
                "location": record["location"]["location_name"],
                "gps": [record["location"]["gps_lat"], record["location"]["gps_lng"]],
            }
        )
        client.publish(str(mqtt_cfg.get("mqtt_topic", "footpath/violations")), payload, qos=1)
        client.disconnect()
        return True
    except Exception:
        return False


def detect_general(frame: np.ndarray, detector: YOLO, conf: float) -> tuple[np.ndarray, int, dict[str, int]]:
    annotated = frame.copy()
    result = detector(annotated, conf=conf, verbose=False)[0]
    total = 0
    class_counts: dict[str, int] = {}

    if result.boxes is None or len(result.boxes) == 0:
        return annotated, total, class_counts

    boxes = result.boxes.xyxy.cpu().numpy().astype(int)
    classes = result.boxes.cls.cpu().numpy().astype(int)
    scores = result.boxes.conf.cpu().numpy()

    for bbox, cls_id, score in zip(boxes, classes, scores):
        x1, y1, x2, y2 = bbox.tolist()
        name = result.names.get(cls_id, str(cls_id))
        total += 1
        class_counts[name.lower()] = class_counts.get(name.lower(), 0) + 1
        color = (0, 200, 255)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            annotated,
            f"{name} {score:.2f}",
            (x1, max(16, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
        )

    return annotated, total, class_counts


def detect_enforcement(
    frame: np.ndarray,
    detector: YOLO,
    lp_model: YOLO | None,
    ocr: Any | None,
    conf: float,
    pixels_per_metre: float,
    fps_cfg: float,
    speed_threshold_kmph: float,
    cooldown_sec: int,
    min_ocr_conf: float,
    cam_cfg: dict[str, Any],
    mqtt_cfg: dict[str, Any],
    enable_mqtt: bool,
) -> tuple[np.ndarray, dict[str, Any], list[dict[str, Any]]]:
    annotated = frame.copy()
    stats = {
        "total": 0,
        "moving_hits": 0,
        "plates_read": 0,
        "violations_saved": 0,
        "class_counts": {},
    }
    events: list[dict[str, Any]] = []

    results = detector.track(frame, persist=True, tracker="bytetrack.yaml", conf=conf, verbose=False)
    if not results or results[0].boxes is None or len(results[0].boxes) == 0:
        return annotated, stats, events

    boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
    classes = results[0].boxes.cls.cpu().numpy().astype(int)
    scores = results[0].boxes.conf.cpu().numpy()
    ids_tensor = results[0].boxes.id
    ids = ids_tensor.cpu().numpy().astype(int) if ids_tensor is not None else np.arange(len(boxes))
    names = results[0].names

    for bbox, cls_id, score, track_id in zip(boxes, classes, scores, ids):
        stats["total"] += 1
        x1, y1, x2, y2 = bbox.tolist()
        class_name = names.get(cls_id, str(cls_id))
        class_key = class_name.lower()
        stats["class_counts"][class_key] = stats["class_counts"].get(class_key, 0) + 1
        test_point = bbox_bottom_center(bbox)

        color = (0, 200, 255)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.circle(annotated, test_point, 4, (255, 255, 255), -1)

        speed_kmph = 0.0
        if class_key in VEHICLE_CLASSES:
            hist = st.session_state.track_history[int(track_id)]
            hist.append(test_point)
            speed_kmph = compute_speed_kmph(hist, pixels_per_metre, fps_cfg)
            if speed_kmph >= speed_threshold_kmph:
                stats["moving_hits"] += 1

        cv2.putText(
            annotated,
            f"id:{track_id} {class_name} {score:.2f} {speed_kmph:.1f}km/h",
            (x1, max(16, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
        )

        if class_key not in VEHICLE_CLASSES or speed_kmph < speed_threshold_kmph:
            continue
        if lp_model is None or ocr is None:
            continue

        vehicle_crop = frame[max(0, y1):max(1, y2), max(0, x1):max(1, x2)]
        if vehicle_crop.size == 0:
            continue

        lp_results = lp_model(vehicle_crop, conf=0.3, verbose=False)[0]
        if lp_results.boxes is None or len(lp_results.boxes) == 0:
            continue

        lp_xyxy = lp_results.boxes.xyxy.cpu().numpy().astype(int)
        lp_conf = lp_results.boxes.conf.cpu().numpy()
        best_idx = max(
            range(len(lp_xyxy)),
            key=lambda i: (float(lp_conf[i]), (lp_xyxy[i][2] - lp_xyxy[i][0]) * (lp_xyxy[i][3] - lp_xyxy[i][1])),
        )

        lx1, ly1, lx2, ly2 = lp_xyxy[best_idx].tolist()
        plate_crop = vehicle_crop[max(0, ly1):max(1, ly2), max(0, lx1):max(1, lx2)]
        if plate_crop.size == 0:
            continue

        stats["plates_read"] += 1
        plate_enhanced = enhance_plate_cpu(plate_crop)
        ocr_res = ocr_with_voting(plate_enhanced, ocr)
        plate_text = str(ocr_res["cleaned_text"])
        ocr_conf = float(ocr_res["confidence"])
        is_valid = bool(ocr_res["is_valid"])

        cv2.rectangle(annotated, (x1 + lx1, y1 + ly1), (x1 + lx2, y1 + ly2), (0, 255, 0), 2)
        cv2.putText(
            annotated,
            f"plate:{plate_text or 'N/A'} conf:{ocr_conf:.2f}",
            (x1, min(annotated.shape[0] - 8, y2 + 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            2,
        )

        now = time.time()
        last_ts = float(st.session_state.last_violation_by_track.get(int(track_id), 0.0))
        if now - last_ts < cooldown_sec:
            continue

        if not (is_valid and ocr_conf >= min_ocr_conf):
            continue

        record = {
            "violation_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "location": {
                "camera_id": cam_cfg.get("camera_id", "FP_CAM_001"),
                "location_name": cam_cfg.get("location_name", "Unknown"),
                "gps_lat": cam_cfg.get("gps_lat", 0.0),
                "gps_lng": cam_cfg.get("gps_lng", 0.0),
            },
            "vehicle": {
                "plate_number": plate_text,
                "plate_ocr_confidence": round(ocr_conf, 3),
                "plate_format_valid": is_valid,
                "vehicle_class": class_name,
                "estimated_speed_kmph": round(speed_kmph, 2),
                "track_id": int(track_id),
            },
            "violation_type": "FOOTPATH_ENCROACHMENT",
            "fine_amount_inr": 500,
            "system": {
                "model_version": "YOLOv8 + ByteTrack + PaddleOCR",
                "pushed_to_dashboard": False,
            },
        }

        out_dir = save_violation(frame, plate_crop, plate_enhanced, record)
        record["system"]["pushed_to_dashboard"] = push_mqtt_if_enabled(record, mqtt_cfg, enable_mqtt)
        st.session_state.last_violation_by_track[int(track_id)] = now
        stats["violations_saved"] += 1

        events.append(
            {
                "time": datetime.now().strftime("%H:%M:%S"),
                "track_id": int(track_id),
                "class": class_name,
                "plate": plate_text,
                "speed_kmph": round(speed_kmph, 1),
                "saved_to": str(out_dir.name),
                "mqtt": "yes" if record["system"]["pushed_to_dashboard"] else "no",
            }
        )

    return annotated, stats, events


def main() -> None:
    st.set_page_config(page_title="Objective 3 - Footpath Enforcement Platform", layout="wide")
    st.title("Objective 3 - Footpath Enforcement Platform")
    st.caption("Continuous live camera detection with full-frame enforcement pipeline: tracking, speed, plate OCR, evidence, and MQTT alerts")

    ensure_state()

    cam_cfg = load_json(
        CONFIG_DIR / "footpath_roi.json",
        {
            "camera_id": "FP_CAM_001",
            "location_name": "Sample Junction",
            "gps_lat": 0.0,
            "gps_lng": 0.0,
        },
    )
    speed_cfg = load_json(CONFIG_DIR / "speed_calibration.json", {"pixels_per_metre": 47.0, "camera_fps": 15.0})
    mqtt_cfg = load_json(
        CONFIG_DIR / "dashboard.json",
        {"mqtt_host": "localhost", "mqtt_port": 1883, "mqtt_topic": "footpath/violations"},
    )
    lab_cfg = load_json(FRONTEND_LAB_CONFIG, {})

    model_options: dict[str, Path] = {}
    if GENERAL_MODEL.exists():
        model_options["General Objects (YOLOv8n)"] = GENERAL_MODEL
    if TWO_WHEELER_MODEL.exists():
        model_options["Two Wheeler Enforcement"] = TWO_WHEELER_MODEL

    if not model_options:
        st.error("No detector models found. Run scripts/download_models.py first.")
        st.stop()

    with st.sidebar:
        st.header("Runtime Controls")
        mode_default = "Footpath Enforcement"
        if str(lab_cfg.get("enablePlatePipeline", True)).lower() in {"false", "0", "no"}:
            mode_default = "General Detection"
        mode_options = ["General Detection", "Footpath Enforcement"]
        mode = st.selectbox("Mode", mode_options, index=mode_options.index(mode_default))
        detector_label = st.selectbox("Detection Model", options=list(model_options.keys()), index=0)
        source_mode = str(lab_cfg.get("sourceMode", "device")).strip().lower()
        source_value = str(lab_cfg.get("sourceValue", "0"))
        camera_index_default = int(source_value) if source_value.isdigit() else 0
        width_default = int(lab_cfg.get("previewWidth", 1280) or 1280)
        height_default = int(lab_cfg.get("previewHeight", 720) or 720)
        conf_default = float(lab_cfg.get("detectionConfidence", 0.35) or 0.35)
        fps_default = int(lab_cfg.get("targetFps", 12) or 12)
        speed_default = float(lab_cfg.get("speedThresholdKmph", 5.0) or 5.0)
        cooldown_default = int(lab_cfg.get("cooldownSec", 60) or 60)
        min_ocr_default = float(lab_cfg.get("minOcrConfidence", 0.65) or 0.65)

        follow_frontend_camera = st.toggle(
            "Follow Frontend Camera Selection",
            value=True,
            help="When enabled, Camera Index tracks frontend Camera Lab Source Value automatically.",
        )

        if source_mode == "device" and follow_frontend_camera:
            desired_camera_index = max(0, min(10, camera_index_default))
            current_camera_index = int(st.session_state.get("camera_index", desired_camera_index))
            if current_camera_index != desired_camera_index:
                st.session_state["camera_index"] = desired_camera_index
                release_camera()
            elif "camera_index" not in st.session_state:
                st.session_state["camera_index"] = desired_camera_index

        if source_mode == "device":
            st.caption(f"Frontend source camera index: {source_value}")
        else:
            st.caption("Frontend source mode is RTSP. Camera Index applies only to local device mode.")

        camera_index = int(st.number_input("Camera Index", min_value=0, max_value=10, step=1, key="camera_index"))
        width = int(st.number_input("Camera Width", min_value=320, max_value=1920, value=max(320, min(1920, width_default)), step=160))
        height = int(st.number_input("Camera Height", min_value=240, max_value=1080, value=max(240, min(1080, height_default)), step=120))

        conf = st.slider("Detection Confidence", min_value=0.10, max_value=0.95, value=max(0.10, min(0.95, conf_default)), step=0.05)
        fps_limit = st.slider("Frame Rate Limit", min_value=2, max_value=30, value=max(2, min(30, fps_default)), step=1)
        max_frame_failures = int(st.slider("Max Consecutive Frame Failures", min_value=2, max_value=30, value=8, step=1))

        st.subheader("Enforcement")
        st.caption("ROI boundary filtering is disabled. The full frame is treated as the enforcement zone.")
        speed_threshold_kmph = st.slider("Speed Threshold (km/h)", min_value=1.0, max_value=20.0, value=max(1.0, min(20.0, speed_default)), step=0.5)
        cooldown_sec = int(st.slider("Per-Track Challan Cooldown (sec)", min_value=10, max_value=300, value=max(10, min(300, cooldown_default)), step=5))
        min_ocr_conf = st.slider("Minimum OCR Confidence", min_value=0.30, max_value=0.95, value=max(0.30, min(0.95, min_ocr_default)), step=0.05)

        plate_possible = LP_MODEL.exists() and PADDLEOCR_AVAILABLE
        if not LP_MODEL.exists():
            st.warning("Plate detector missing: models/lp_localiser.pt")
        if not PADDLEOCR_AVAILABLE:
            st.warning("paddleocr not installed; plate OCR disabled.")
        enable_plate_pipeline = st.toggle(
            "Enable Plate Detection + OCR",
            value=bool(lab_cfg.get("enablePlatePipeline", plate_possible)) if plate_possible else False,
            disabled=not plate_possible,
        )

        mqtt_possible = PAHO_AVAILABLE
        if not mqtt_possible:
            st.info("paho-mqtt not installed; dashboard push disabled.")
        enable_mqtt = st.toggle("Enable MQTT Dashboard Push", value=False, disabled=not mqtt_possible)

        c1, c2, c3 = st.columns(3)
        if c1.button("Start", use_container_width=True):
            st.session_state.running = True
        if c2.button("Stop", use_container_width=True):
            st.session_state.running = False
            release_camera()
        if c3.button("Reconnect", use_container_width=True):
            release_camera()
            st.session_state.frame_failures = 0

    detector_model_path = str(model_options[detector_label])
    use_plate = mode == "Footpath Enforcement" and enable_plate_pipeline
    detector, lp_model, ocr = load_models(detector_model_path, use_plate)

    frame_slot = st.empty()
    stats_slot = st.empty()
    event_slot = st.empty()

    if not st.session_state.running:
        export_metrics(
            {
                "mode": mode,
                "status": "idle",
                "detected": 0,
                "moving_hits": 0,
                "plates_read": 0,
                "violations_saved": 0,
                "class_counts": {},
            },
            0.0,
        )
        st.info("Press Start to begin continuous live detection.")
        return

    frame, status = read_frame_with_recovery(camera_index, width, height, max_frame_failures)
    if frame is None:
        if status == "camera_open_failed":
            stats_slot.error("Camera open failed. Check camera index and close other apps using the camera.")
        elif status == "reconnect_failed":
            stats_slot.warning("Frame read failed repeatedly. Reconnect attempt failed; retrying.")
        else:
            stats_slot.warning(
                f"Temporary frame read failure {st.session_state.frame_failures}/{max_frame_failures}. Auto-retrying..."
            )
        export_metrics(
            {
                "mode": mode,
                "status": "waiting_frame",
                "detected": 0,
                "moving_hits": 0,
                "plates_read": 0,
                "violations_saved": 0,
                "class_counts": {},
            },
            0.0,
        )
        time.sleep(0.2)
        st.rerun()
        return

    t0 = time.time()
    if mode == "General Detection":
        annotated, total, class_counts = detect_general(frame, detector, conf)
        stats = {
            "mode": mode,
            "detected": total,
            "moving_hits": 0,
            "plates_read": 0,
            "violations_saved": 0,
            "reconnects": st.session_state.reconnects,
            "camera_failures": st.session_state.frame_failures,
            "class_counts": class_counts,
        }
        events = []
    else:
        annotated, enforcement_stats, events = detect_enforcement(
            frame,
            detector,
            lp_model,
            ocr,
            conf,
            float(speed_cfg.get("pixels_per_metre", 47.0)),
            float(speed_cfg.get("camera_fps", 15.0)),
            float(speed_threshold_kmph),
            int(cooldown_sec),
            float(min_ocr_conf),
            cam_cfg,
            mqtt_cfg,
            enable_mqtt,
        )
        stats = {
            "mode": mode,
            "detected": enforcement_stats["total"],
            "moving_hits": enforcement_stats["moving_hits"],
            "plates_read": enforcement_stats["plates_read"],
            "violations_saved": enforcement_stats["violations_saved"],
            "reconnects": st.session_state.reconnects,
            "camera_failures": st.session_state.frame_failures,
            "class_counts": enforcement_stats["class_counts"],
        }

    elapsed = max(time.time() - t0, 1e-6)
    stats["inference_fps"] = round(1.0 / elapsed, 1)

    render_frame(frame_slot, annotated)
    export_preview_frame(annotated)
    display_stats = {k: v for k, v in stats.items() if k != "class_counts"}
    stats_slot.success(" | ".join([f"{k}: {v}" for k, v in display_stats.items()]))

    if events:
        st.session_state.events = (events + st.session_state.events)[:25]
    if st.session_state.events:
        event_slot.dataframe(st.session_state.events, use_container_width=True)

    export_metrics(stats, elapsed * 1000.0)

    time.sleep(max(0.0, (1.0 / fps_limit) - elapsed))
    st.rerun()


if __name__ == "__main__":
    main()
