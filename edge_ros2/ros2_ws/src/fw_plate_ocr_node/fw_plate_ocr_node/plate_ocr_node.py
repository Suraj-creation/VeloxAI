"""
fw_plate_ocr_node — Stages 4, 5, 6: Plate Localisation + Enhancement + OCR
============================================================================
Subscribes to:
  /fw/camera/frame  (CompressedImage from fw_sensor_bridge)
  /fw/track/speed   (TrackResultArray from fw_tracking_speed_node)

Publishes:
  /fw/plate/ocr     (PlateOcr — one message per moving track)

Design:
  - Maintains a rolling frame buffer keyed by frame_id (UUID)
  - When a TrackResultArray arrives, looks up the frame whose frame_id
    matches the track batch's frame_id. Falls back to the most-recent frame
    if not found (accommodates small inter-node timing jitter on Pi).
  - For each moving track, runs Stage 4 → 5 → 6 pipeline.
  - Uses get_best_plate() to select highest-conf plate with area tiebreaker
    (matches ML guide Section 7).
  - min_plate_px_width = 80 (ML guide minimum for reliable OCR).
  - Never opens the camera device directly.
"""

from __future__ import annotations

import json
import re
import time
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from sensor_msgs.msg import CompressedImage
from builtin_interfaces.msg import Time as RosTime

from fw_msgs.msg import TrackResultArray, TrackResult, PlateOcr
from fw_sensor_bridge.sensor_bridge_node import parse_frame_header

NODE_NAME = "fw_plate_ocr_node"
TRACK_SUB = "/fw/track/speed"
FRAME_SUB = "/fw/camera/frame"
PUB_TOPIC = "/fw/plate/ocr"

# Indian LP regex patterns
VALID_LP_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$")
BH_LP_RE = re.compile(r"^[0-9]{2}BH[0-9]{4}[A-Z]{2}$")

# Position-aware confusion maps (ML guide Section 9)
OCR_L2D = {"O": "0", "I": "1", "l": "1",
            "Z": "2", "S": "5", "B": "8", "G": "6"}
OCR_D2L = {"0": "O", "1": "I", "5": "S", "8": "B", "6": "G"}

# Frame buffer capacity: ring buffer of latest N frames
FRAME_BUFFER_SIZE = 8


def load_json_safe(path: Path, fallback: dict) -> dict:
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return fallback


# ─── Stage 4: Best-plate selection (ML Guide §7) ─────────────────────────────

def get_best_plate(plate_detections: list[dict]) -> Optional[dict]:
    """
    From a list of plate detections, return the best one.
    Sort by confidence descending; use bbox area as tiebreaker.
    Each detection: {'x1':, 'y1':, 'x2':, 'y2':, 'confidence':}
    """
    if not plate_detections:
        return None
    return sorted(
        plate_detections,
        key=lambda d: (
            d["confidence"],
            (d["x2"] - d["x1"]) * (d["y2"] - d["y1"]),
        ),
        reverse=True,
    )[0]


# ─── Stage 4: Plate Localiser ─────────────────────────────────────────────────

class PlateLocaliser:
    """
    YOLOv8n fine-tuned on Indian LP dataset.
    Input:  vehicle crop (BGR), resized to 320×320 for inference
    Output: list of plate detections (all candidates, caller picks best)
    """

    def __init__(self, model_path: Path, conf: float = 0.30):
        if not model_path.exists():
            raise RuntimeError(
                f"[{NODE_NAME}] LP localiser model not found: {model_path}")
        from ultralytics import YOLO
        self._model = YOLO(str(model_path))
        self._conf = conf

    def localise(self, vehicle_crop: np.ndarray) -> list[dict]:
        """Returns all detected plate bboxes (scaled to crop coords)."""
        if vehicle_crop is None or vehicle_crop.size == 0:
            return []

        resized = cv2.resize(vehicle_crop, (320, 320))
        results = self._model(resized, conf=self._conf, verbose=False)

        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            return []

        boxes = results[0].boxes.xyxy.cpu().numpy().astype(float)
        scores = results[0].boxes.conf.cpu().numpy()

        # Scale back from 320×320 to original crop size
        h, w = vehicle_crop.shape[:2]
        sx = w / 320.0
        sy = h / 320.0

        detections = []
        for (lx1, ly1, lx2, ly2), score in zip(boxes, scores):
            detections.append({
                "x1": int(lx1 * sx),
                "y1": int(ly1 * sy),
                "x2": int(lx2 * sx),
                "y2": int(ly2 * sy),
                "confidence": float(score),
            })
        return detections


# ─── Stage 5: Plate Enhancer (ML Guide §8 Option A) ──────────────────────────

class PlateEnhancer:
    """
    Two-path plate enhancer:
      clahe_cpu — fast classical pipeline for Raspberry Pi 4  (<10ms)
      esrgan    — neural SR for Jetson Nano (loaded only if model present)
    """

    def __init__(self, esrgan_path: Optional[Path] = None):
        self._esrgan_interp = None
        if esrgan_path and esrgan_path.exists():
            self._load_esrgan(esrgan_path)

    def _load_esrgan(self, path: Path) -> None:
        try:
            try:
                import tflite_runtime.interpreter as tflite
            except ImportError:
                import tensorflow.lite as tflite  # type: ignore
            self._esrgan_interp = tflite.Interpreter(
                str(path), num_threads=4)
            self._esrgan_interp.allocate_tensors()
            self._in_det = self._esrgan_interp.get_input_details()
            self._out_det = self._esrgan_interp.get_output_details()
        except Exception:
            self._esrgan_interp = None

    def enhance_clahe(self, plate_img: np.ndarray,
                      target_width: int = 400) -> np.ndarray:
        """Full classical CPU pipeline. <10ms on Pi 4 (ML Guide §8)."""
        h, w = plate_img.shape[:2]
        if w == 0 or h == 0:
            return plate_img
        # Step 1: Upscale to target width (bicubic — ML guide)
        scale = max(target_width / w, 1.0)
        new_w = max(target_width, w)
        new_h = max(32, int(h * scale))
        upscaled = cv2.resize(plate_img, (new_w, new_h),
                              interpolation=cv2.INTER_CUBIC)
        # Step 2: Grayscale
        gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
        # Step 3: CLAHE
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
        enhanced = clahe.apply(gray)
        # Step 4: Blur for unsharp mask
        blurred = cv2.GaussianBlur(enhanced, (0, 0), 1.5)
        # Step 5: Unsharp mask
        sharpened = cv2.addWeighted(enhanced, 1.8, blurred, -0.8, 0)
        # Step 6: Bilateral filter
        denoised = cv2.bilateralFilter(sharpened, d=5,
                                       sigmaColor=40, sigmaSpace=40)
        return cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)

    def deskew(self, plate_img: np.ndarray) -> np.ndarray:
        """Hough-line deskew — corrects tilt <20°."""
        if plate_img is None or plate_img.size == 0:
            return plate_img
        gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=60)
        if lines is None:
            return plate_img
        angles = []
        for line in lines[:5]:
            rho, theta = line[0]
            angle = np.degrees(theta) - 90
            if abs(angle) < 20:
                angles.append(angle)
        if not angles:
            return plate_img
        median_angle = float(np.median(angles))
        if abs(median_angle) < 1.0:
            return plate_img
        h, w = plate_img.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), median_angle, 1.0)
        return cv2.warpAffine(plate_img, M, (w, h),
                              flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)

    def enhance(self, plate_img: np.ndarray) -> tuple[np.ndarray, str]:
        """
        Returns (enhanced_image, method_used).
        Prefers ESRGAN if available (Jetson), else CLAHE CPU (Pi).
        """
        if self._esrgan_interp is not None:
            result = self._enhance_esrgan(plate_img)
            if result is not None:
                return result, "esrgan"
        deskewed = self.deskew(plate_img)
        return self.enhance_clahe(deskewed), "clahe_cpu"

    def _enhance_esrgan(self, plate_img: np.ndarray) -> Optional[np.ndarray]:
        try:
            inp = cv2.resize(plate_img, (256, 64))
            inp = inp.astype(np.float32) / 255.0
            inp = np.expand_dims(inp, axis=0)
            self._esrgan_interp.set_tensor(
                self._in_det[0]["index"], inp)
            self._esrgan_interp.invoke()
            out = self._esrgan_interp.get_tensor(
                self._out_det[0]["index"])
            out = np.squeeze(out, axis=0)
            return np.clip(out * 255.0, 0, 255).astype(np.uint8)
        except Exception:
            return None


# ─── Stage 6: PaddleOCR Engine (ML Guide §9) ─────────────────────────────────

class IndianPlateOCR:
    """
    PaddleOCR wrapper with 3-round augmentation voting and
    position-aware confusion correction (ML Guide §9).
    """

    def __init__(self, models_dir: Path, use_gpu: bool = False):
        rec_dir = str(models_dir / "paddleocr_rec") if (
            models_dir / "paddleocr_rec").exists() else None
        det_dir = str(models_dir / "paddleocr_det") if (
            models_dir / "paddleocr_det").exists() else None
        cls_dir = str(models_dir / "paddleocr_cls") if (
            models_dir / "paddleocr_cls").exists() else None

        from paddleocr import PaddleOCR
        self._ocr = PaddleOCR(
            use_angle_cls=True,
            lang="en",
            use_gpu=use_gpu,
            rec_model_dir=rec_dir,
            det_model_dir=det_dir,
            cls_model_dir=cls_dir,
            show_log=False,
        )

    def read_plate(self, plate_img: np.ndarray) -> dict:
        """Run OCR → structured result."""
        try:
            result = self._ocr.ocr(plate_img, cls=True)
        except Exception as exc:
            return {"raw_text": "", "cleaned_text": "",
                    "is_valid": False, "confidence": 0.0,
                    "error": str(exc)}
        if not result or not result[0]:
            return {"raw_text": "", "cleaned_text": "",
                    "is_valid": False, "confidence": 0.0}

        all_text = ""
        total_conf = 0.0
        count = 0
        for line in result[0]:
            text, confidence = line[1]
            all_text += text
            total_conf += confidence
            count += 1

        avg_conf = total_conf / count if count > 0 else 0.0
        cleaned = self._clean(all_text)
        return {
            "raw_text": all_text,
            "cleaned_text": cleaned,
            "is_valid": self._validate(cleaned),
            "confidence": round(avg_conf, 3),
        }

    def read_with_voting(self, plate_img: np.ndarray,
                         n_rounds: int = 3) -> dict:
        """3-round augmentation voting (ML Guide §9)."""
        augmentations = [
            lambda x: x,
            lambda x: cv2.convertScaleAbs(x, alpha=1.1, beta=10),
            lambda x: cv2.convertScaleAbs(x, alpha=0.9, beta=-10),
        ]
        candidates = []
        for aug in augmentations[:n_rounds]:
            res = self.read_plate(aug(plate_img))
            if res.get("is_valid"):
                candidates.append(res)
        return (max(candidates, key=lambda r: r["confidence"])
                if candidates else self.read_plate(plate_img))

    @staticmethod
    def _clean(raw: str) -> str:
        """Position-aware confusion correction (ML Guide §9)."""
        text = raw.upper().replace(" ", "").replace("-", "").strip()
        text = re.sub(r"[^A-Z0-9]", "", text)
        if len(text) >= 10:
            c = list(text)
            for pos in [2, 3]:             # district digits
                c[pos] = OCR_L2D.get(c[pos], c[pos])
            for pos in [0, 1, 4, 5]:       # state + series letters
                c[pos] = OCR_D2L.get(c[pos], c[pos])
            for pos in range(6, min(10, len(c))):  # registration digits
                c[pos] = OCR_L2D.get(c[pos], c[pos])
            text = "".join(c)
        return text

    @staticmethod
    def _validate(text: str) -> bool:
        return bool(VALID_LP_RE.match(text) or BH_LP_RE.match(text))


# ─── Rolling frame buffer ─────────────────────────────────────────────────────

class FrameRingBuffer:
    """
    Ordered dict ring buffer: frame_id → (frame, monotonic_ts).
    Max capacity FRAME_BUFFER_SIZE. Evicts oldest on overflow.
    Thread-safe.
    """

    def __init__(self, capacity: int = FRAME_BUFFER_SIZE):
        self._buf: OrderedDict[str, tuple[np.ndarray, float]] = OrderedDict()
        self._cap = capacity
        self._lock = threading.Lock()

    def put(self, frame_id: str, frame: np.ndarray) -> None:
        with self._lock:
            if frame_id in self._buf:
                self._buf.move_to_end(frame_id)
            else:
                if len(self._buf) >= self._cap:
                    self._buf.popitem(last=False)
            self._buf[frame_id] = (frame, time.monotonic())

    def get(self, frame_id: str) -> Optional[np.ndarray]:
        with self._lock:
            entry = self._buf.get(frame_id)
            return entry[0] if entry is not None else None

    def latest(self) -> Optional[np.ndarray]:
        with self._lock:
            if not self._buf:
                return None
            return next(reversed(self._buf.values()))[0]


# ─── ROS2 Node ────────────────────────────────────────────────────────────────

class FwPlateOcrNode(Node):

    def __init__(self) -> None:
        super().__init__(NODE_NAME)

        self.declare_parameter("config_dir", "/config")
        self.declare_parameter("models_dir", "/models")
        self.declare_parameter("device_id", "EDGE-001")
        self.declare_parameter("camera_id", "FP_CAM_001")

        cfg_dir = Path(self.get_parameter("config_dir").value)
        mdl_dir = Path(self.get_parameter("models_dir").value)
        self._camera_id = str(self.get_parameter("camera_id").value)

        thresh_cfg = load_json_safe(cfg_dir / "thresholds.json", {})
        self._lp_conf = float(thresh_cfg.get("lp_localiser_conf", 0.30))
        self._min_plate_px_width = int(
            thresh_cfg.get("min_plate_px_width", 80))  # ML guide minimum
        self._min_ocr_conf = float(thresh_cfg.get("min_ocr_confidence", 0.65))

        # ── Load Stage 4 — LP localiser ───────────────────────────────────────
        lp_path = mdl_dir / "lp_localiser.pt"
        try:
            self._localiser = PlateLocaliser(lp_path, conf=self._lp_conf)
            self.get_logger().info(f"[{NODE_NAME}] LP localiser loaded.")
        except RuntimeError as e:
            self.get_logger().warn(str(e) + " — OCR will be skipped.")
            self._localiser = None

        # ── Load Stage 6 — PaddleOCR ─────────────────────────────────────────
        try:
            self._ocr_engine = IndianPlateOCR(mdl_dir, use_gpu=False)
            self.get_logger().info(f"[{NODE_NAME}] PaddleOCR ready.")
        except Exception as e:
            self.get_logger().error(f"[{NODE_NAME}] OCR init failed: {e}")
            self._ocr_engine = None

        # ── Load Stage 5 — Enhancer ───────────────────────────────────────────
        esrgan_path = mdl_dir / "esrgan_tiny.tflite"
        self._enhancer = PlateEnhancer(
            esrgan_path if esrgan_path.exists() else None)

        # Frame ring buffer (populated from /fw/camera/frame)
        self._frame_buf = FrameRingBuffer(FRAME_BUFFER_SIZE)

        # QoS
        frame_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1,
        )
        track_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=5,
        )

        self._pub = self.create_publisher(PlateOcr, PUB_TOPIC, track_qos)

        # Subscribe to camera frames FIRST so buffer is ready for track msgs
        self._frame_sub = self.create_subscription(
            CompressedImage, FRAME_SUB, self._on_frame, frame_qos)

        self._track_sub = self.create_subscription(
            TrackResultArray, TRACK_SUB, self._on_tracks, track_qos)

        self.get_logger().info(
            f"[{NODE_NAME}] Ready. sub_frame={FRAME_SUB} "
            f"sub_track={TRACK_SUB} pub_ocr={PUB_TOPIC}"
        )

    # ── Frame callback: buffer frames keyed by UUID frame_id ─────────────────

    def _on_frame(self, msg: CompressedImage) -> None:
        meta = parse_frame_header(msg.header.frame_id)
        if not meta["signal_ok"]:
            return  # discard flat/bad frames

        buf = np.frombuffer(msg.data, dtype=np.uint8)
        frame = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if frame is not None:
            self._frame_buf.put(meta["frame_id"], frame)

    # ── Track callback ────────────────────────────────────────────────────────

    def _on_tracks(self, msg: TrackResultArray) -> None:
        # Look up frame by exact frame_id; fall back to most-recent
        frame = self._frame_buf.get(msg.frame_id)
        if frame is None:
            frame = self._frame_buf.latest()
        if frame is None:
            return  # no frame available yet

        for track in msg.tracks:
            if not track.is_moving:
                continue  # parked → skip OCR (ML Guide §6)
            self._process_track(track, frame, msg.frame_id)

    def _process_track(self, track: TrackResult,
                       frame: np.ndarray,
                       frame_id: str) -> None:
        now = self.get_clock().now()
        ocr_msg = self._empty_ocr_msg(now, frame_id, track.track_id)

        # Crop vehicle region
        h_f, w_f = frame.shape[:2]
        x1 = max(0, int(track.x1))
        y1 = max(0, int(track.y1))
        x2 = min(w_f - 1, int(track.x2))
        y2 = min(h_f - 1, int(track.y2))
        vehicle_crop = frame[y1:y2, x1:x2]

        if vehicle_crop is None or vehicle_crop.size == 0:
            self._pub.publish(ocr_msg)
            return

        # ── Stage 4: Plate localisation ───────────────────────────────────────
        t0 = time.perf_counter()
        all_plates = (self._localiser.localise(vehicle_crop)
                      if self._localiser else [])
        ocr_msg.plate_loc_latency_ms = float(
            (time.perf_counter() - t0) * 1000.0)

        # get_best_plate: highest conf, area tiebreaker (ML guide §7)
        plate_det = get_best_plate(all_plates)

        if plate_det is None:
            self._pub.publish(ocr_msg)
            return

        lx1 = max(0, plate_det["x1"])
        ly1 = max(0, plate_det["y1"])
        lx2 = min(vehicle_crop.shape[1] - 1, plate_det["x2"])
        ly2 = min(vehicle_crop.shape[0] - 1, plate_det["y2"])
        plate_crop_raw = vehicle_crop[ly1:ly2, lx1:lx2]

        plate_w = lx2 - lx1
        if plate_crop_raw.size == 0 or plate_w < self._min_plate_px_width:
            self._pub.publish(ocr_msg)
            return

        ocr_msg.plate_found = True
        # Absolute coords in full frame
        ocr_msg.plate_x1 = float(x1 + lx1)
        ocr_msg.plate_y1 = float(y1 + ly1)
        ocr_msg.plate_x2 = float(x1 + lx2)
        ocr_msg.plate_y2 = float(y1 + ly2)
        ocr_msg.plate_localiser_confidence = float(plate_det["confidence"])

        # ── Stage 5: Enhancement ─────────────────────────────────────────────
        t1 = time.perf_counter()
        plate_crop_enhanced, method = self._enhancer.enhance(plate_crop_raw)
        ocr_msg.enhancement_latency_ms = float(
            (time.perf_counter() - t1) * 1000.0)
        ocr_msg.enhancement_method = method

        # ── Stage 6: OCR with voting ──────────────────────────────────────────
        if self._ocr_engine is None:
            self._pub.publish(ocr_msg)
            return

        t2 = time.perf_counter()
        ocr_result = self._ocr_engine.read_with_voting(
            plate_crop_enhanced, n_rounds=3)
        ocr_msg.ocr_latency_ms = float(
            (time.perf_counter() - t2) * 1000.0)

        ocr_msg.raw_text = str(ocr_result.get("raw_text", ""))
        ocr_msg.cleaned_text = str(ocr_result.get("cleaned_text", ""))
        ocr_msg.format_valid = bool(ocr_result.get("is_valid", False))
        ocr_msg.ocr_confidence = float(ocr_result.get("confidence", 0.0))
        ocr_msg.ocr_voting_rounds = 3

        self._pub.publish(ocr_msg)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _empty_ocr_msg(self, now, frame_id: str,
                       track_id: int) -> PlateOcr:
        msg = PlateOcr()
        msg.timestamp = self._ros_time(now)
        msg.camera_id = self._camera_id
        msg.frame_id = frame_id
        msg.track_id = track_id
        msg.plate_found = False
        msg.format_valid = False
        msg.ocr_confidence = 0.0
        return msg

    @staticmethod
    def _ros_time(stamp) -> RosTime:
        ros_t = RosTime()
        t_ns = stamp.nanoseconds
        ros_t.sec = int(t_ns // 1_000_000_000)
        ros_t.nanosec = int(t_ns % 1_000_000_000)
        return ros_t

    def destroy_node(self) -> None:
        self.get_logger().info(f"[{NODE_NAME}] Shutting down.")
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = FwPlateOcrNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
