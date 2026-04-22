"""
fw_inference_node — Stage 1 Two-Wheeler Detection
==================================================
Subscribes to /fw/camera/frame (CompressedImage published by fw_sensor_bridge).
Does NOT open the camera device — single responsibility.

Responsibilities:
  - Subscribe to /fw/camera/frame
  - Decode JPEG → BGR
  - Run YOLOv8n / ONNX / TFLite INT8 detection
  - Filter to two-wheeler classes + min bbox area
  - Publish DetectionArray on /fw/detect/twowheeler (preserves frame_id)

ROS2 Topics Subscribed:
  /fw/camera/frame  (sensor_msgs/CompressedImage)

ROS2 Topics Published:
  /fw/detect/twowheeler  (fw_msgs/DetectionArray)

Config: /config/camera_lab.json, /config/thresholds.json
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import (QoSProfile, QoSReliabilityPolicy,
                        QoSHistoryPolicy)
from sensor_msgs.msg import CompressedImage
from builtin_interfaces.msg import Time as RosTime

from fw_msgs.msg import Detection, DetectionArray
from fw_sensor_bridge.sensor_bridge_node import parse_frame_header

NODE_NAME = "fw_inference_node"
FRAME_SUB = "/fw/camera/frame"
DETECT_PUB = "/fw/detect/twowheeler"

TWOWHEELER_CLASSES = {
    "motorcycle", "bicycle", "scooter", "e-scooter",
    "motorbike", "bike", "moped", "two-wheeler",
}
COCO_TWOWHEELER_IDS = {1, 3}   # bicycle=1, motorcycle=3 in COCO


def load_json_safe(path: Path, fallback: dict) -> dict:
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else fallback
    except Exception:
        pass
    return fallback


# ─── YOLO Detector Engine ─────────────────────────────────────────────────────

class DetectorEngine:
    """
    Multi-backend YOLO wrapper.
    Supports: PyTorch (.pt), ONNX Runtime (.onnx), TFLite INT8 (.tflite).
    Raises RuntimeError on missing model file.
    """

    def __init__(self, model_path: Path, conf: float = 0.45,
                 iou: float = 0.50, input_size: int = 320):
        if not model_path.exists():
            raise RuntimeError(
                f"[{NODE_NAME}] Model not found: {model_path}\n"
                "Place model file in /models/ volume before starting.")

        self.conf = conf
        self.iou = iou
        self.input_size = input_size
        self._suffix = model_path.suffix.lower()

        if self._suffix in (".pt", ".torchscript"):
            from ultralytics import YOLO
            self._model = YOLO(str(model_path))
            self._backend = "ultralytics"

        elif self._suffix == ".onnx":
            import onnxruntime as ort
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            avail = ort.get_available_providers()
            providers = [p for p in providers if p in avail] or ["CPUExecutionProvider"]
            sess_opts = ort.SessionOptions()
            sess_opts.inter_op_num_threads = 4
            sess_opts.intra_op_num_threads = 4
            self._session = ort.InferenceSession(
                str(model_path), sess_options=sess_opts, providers=providers)
            self._input_name = self._session.get_inputs()[0].name
            self._backend = "onnx"

        elif self._suffix == ".tflite":
            try:
                import tflite_runtime.interpreter as tflite
            except ImportError:
                import tensorflow.lite as tflite  # type: ignore
            self._interp = tflite.Interpreter(
                str(model_path), num_threads=4)
            self._interp.allocate_tensors()
            self._in_details = self._interp.get_input_details()
            self._out_details = self._interp.get_output_details()
            self._backend = "tflite"
        else:
            raise RuntimeError(f"Unsupported model format: {self._suffix}")

    def detect(self, frame: np.ndarray) -> list[dict]:
        """Run detection. Returns list of {class_id, class_name, confidence, x1, y1, x2, y2, area}."""
        if self._backend == "ultralytics":
            return self._detect_ultralytics(frame)
        elif self._backend == "onnx":
            return self._detect_onnx(frame)
        elif self._backend == "tflite":
            return self._detect_tflite(frame)
        return []

    # ── Ultralytics ────────────────────────────────────────────────────────────

    def _detect_ultralytics(self, frame: np.ndarray) -> list[dict]:
        results = self._model(
            frame, conf=self.conf, iou=self.iou,
            imgsz=self.input_size, verbose=False)
        out = []
        if not results or results[0].boxes is None:
            return out
        boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
        cls_ids = results[0].boxes.cls.cpu().numpy().astype(int)
        confs_np = results[0].boxes.conf.cpu().numpy()
        names = results[0].names
        for bbox, cls_id, conf_val in zip(boxes, cls_ids, confs_np):
            x1, y1, x2, y2 = bbox.tolist()
            name = names.get(int(cls_id), str(cls_id)).lower()
            area = max(0, (x2 - x1)) * max(0, (y2 - y1))
            out.append({
                "class_id": int(cls_id), "class_name": name,
                "confidence": float(conf_val),
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "area": float(area),
            })
        return out

    # ── ONNX ───────────────────────────────────────────────────────────────────

    def _detect_onnx(self, frame: np.ndarray) -> list[dict]:
        inp = self._preprocess(frame)
        outputs = self._session.run(None, {self._input_name: inp})
        return self._postprocess_yolo(outputs[0], frame.shape)

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        resized = cv2.resize(frame, (self.input_size, self.input_size))
        resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        inp = resized.astype(np.float32) / 255.0
        return np.expand_dims(np.transpose(inp, (2, 0, 1)), axis=0)

    def _postprocess_yolo(self, output: np.ndarray,
                           orig_shape: tuple) -> list[dict]:
        detections = []
        orig_h, orig_w = orig_shape[:2]
        sx = orig_w / self.input_size
        sy = orig_h / self.input_size

        if output.ndim == 3:
            pred = np.squeeze(output, axis=0)
            if pred.shape[0] < pred.shape[1]:
                pred = pred.T
            boxes_xywh = pred[:, :4]
            class_scores = pred[:, 4:]
            cls_ids = np.argmax(class_scores, axis=1)
            confs = class_scores[np.arange(len(cls_ids)), cls_ids]
            mask = confs >= self.conf
            for (cx, cy, w, h), cls_id, conf_val in zip(
                    boxes_xywh[mask], cls_ids[mask], confs[mask]):
                x1 = int((cx - w / 2) * sx)
                y1 = int((cy - h / 2) * sy)
                x2 = int((cx + w / 2) * sx)
                y2 = int((cy + h / 2) * sy)
                area = max(0, x2 - x1) * max(0, y2 - y1)
                detections.append({
                    "class_id": int(cls_id), "class_name": str(int(cls_id)),
                    "confidence": float(conf_val),
                    "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "area": float(area),
                })
        return detections

    # ── TFLite ─────────────────────────────────────────────────────────────────

    def _detect_tflite(self, frame: np.ndarray) -> list[dict]:
        inp_detail = self._in_details[0]
        h, w = inp_detail["shape"][1], inp_detail["shape"][2]
        resized = cv2.resize(frame, (w, h))
        resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        inp = (resized.astype(np.uint8)
               if inp_detail["dtype"] == np.uint8
               else resized.astype(np.float32) / 255.0)
        self._interp.set_tensor(inp_detail["index"],
                                np.expand_dims(inp, axis=0))
        self._interp.invoke()

        orig_h, orig_w = frame.shape[:2]
        out_boxes = self._interp.get_tensor(self._out_details[0]["index"])
        out_classes = self._interp.get_tensor(self._out_details[1]["index"])
        out_scores = self._interp.get_tensor(self._out_details[2]["index"])
        out_count = int(self._interp.get_tensor(
            self._out_details[3]["index"])[0])

        detections = []
        for i in range(out_count):
            score = float(out_scores[0][i])
            if score < self.conf:
                continue
            cls_id = int(out_classes[0][i])
            y1r, x1r, y2r, x2r = out_boxes[0][i]
            x1 = int(x1r * orig_w)
            y1 = int(y1r * orig_h)
            x2 = int(x2r * orig_w)
            y2 = int(y2r * orig_h)
            detections.append({
                "class_id": cls_id, "class_name": str(cls_id),
                "confidence": score,
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "area": float(max(0, x2-x1) * max(0, y2-y1)),
            })
        return detections

    # ── Two-wheeler filter ─────────────────────────────────────────────────────

    @staticmethod
    def filter_twowheelers(detections: list[dict],
                            min_area: float = 1500.0) -> list[dict]:
        """Filter to two-wheeler classes above minimum bbox area."""
        out = []
        for d in detections:
            if d.get("area", 0.0) < min_area:
                continue
            name = d.get("class_name", "").lower().strip()
            cls_id = d.get("class_id", -1)
            if any(tw in name for tw in TWOWHEELER_CLASSES):
                out.append(d)
                continue
            if cls_id in COCO_TWOWHEELER_IDS:
                d["class_name"] = "motorcycle" if cls_id == 3 else "bicycle"
                out.append(d)
        return out


# ─── ROS2 Node ────────────────────────────────────────────────────────────────

class FwInferenceNode(Node):

    def __init__(self) -> None:
        super().__init__(NODE_NAME)

        self.declare_parameter("config_dir", "/config")
        self.declare_parameter("models_dir", "/models")
        self.declare_parameter("device_id", "EDGE-001")
        self.declare_parameter("camera_id", "FP_CAM_001")

        cfg_dir = Path(self.get_parameter("config_dir").value)
        mdl_dir = Path(self.get_parameter("models_dir").value)
        self._device_id = str(self.get_parameter("device_id").value)
        self._camera_id = str(self.get_parameter("camera_id").value)

        thresh_cfg = load_json_safe(cfg_dir / "thresholds.json", {})
        lab_cfg = load_json_safe(cfg_dir / "camera_lab.json", {})

        model_name = lab_cfg.get("model_file", "twowheeler_yolov8n.pt")
        conf = float(thresh_cfg.get("detection_confidence", 0.45))
        iou = float(thresh_cfg.get("nms_iou", 0.50))
        input_sz = int(thresh_cfg.get("detection_input_size", 320))
        self._min_bbox_area = float(thresh_cfg.get("min_bbox_area_px", 1500.0))

        model_path = mdl_dir / model_name
        try:
            self._detector = DetectorEngine(model_path, conf=conf,
                                            iou=iou, input_size=input_sz)
            self.get_logger().info(
                f"[{NODE_NAME}] Model loaded: {model_path.name} "
                f"backend={self._detector._backend}"
            )
        except RuntimeError as exc:
            self.get_logger().error(str(exc))
            raise

        self._frame_count = 0
        self._pipeline_errors = 0

        # QoS — match sensor_bridge's BEST_EFFORT for frames
        frame_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1,
        )
        out_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=5,
        )

        self._pub = self.create_publisher(DetectionArray, DETECT_PUB, out_qos)
        self._sub = self.create_subscription(
            CompressedImage, FRAME_SUB, self._on_frame, frame_qos)

        self.get_logger().info(
            f"[{NODE_NAME}] Ready. Subscribed={FRAME_SUB} "
            f"Publishing={DETECT_PUB}"
        )

    def _on_frame(self, msg: CompressedImage) -> None:
        # Parse header metadata from sensor_bridge
        header_meta = parse_frame_header(msg.header.frame_id)
        frame_id = header_meta["frame_id"]
        signal_ok = header_meta["signal_ok"]
        mean_luma = header_meta["mean_luma"]
        std_luma = header_meta["std_luma"]
        frame_number = header_meta["frame_number"]

        self._frame_count += 1

        # Decode JPEG
        buf = np.frombuffer(msg.data, dtype=np.uint8)
        frame = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if frame is None:
            self._publish_empty(frame_id, frame_number, signal_ok,
                                mean_luma, std_luma, latency_ms=0.0)
            return

        t0 = time.perf_counter()
        dets: list[dict] = []

        if signal_ok:
            try:
                raw = self._detector.detect(frame)
                dets = DetectorEngine.filter_twowheelers(
                    raw, min_area=self._min_bbox_area)
            except Exception as exc:
                self._pipeline_errors += 1
                self.get_logger().error(
                    f"[{NODE_NAME}] Detection error frame={frame_number}: {exc}")

        latency_ms = (time.perf_counter() - t0) * 1000.0

        # Build DetectionArray
        out = DetectionArray()
        now = self.get_clock().now()
        out.frame_timestamp = self._ros_time(now)
        out.camera_id = self._camera_id
        out.frame_id = frame_id
        out.frame_number = frame_number
        out.signal_mean_luma = float(mean_luma)
        out.signal_std_luma = float(std_luma)
        out.signal_ok = signal_ok
        out.stage1_latency_ms = float(latency_ms)

        for d in dets:
            det = Detection()
            det.timestamp = self._ros_time(now)
            det.camera_id = self._camera_id
            det.track_id = -1  # assigned by tracking node
            det.x1 = float(d["x1"])
            det.y1 = float(d["y1"])
            det.x2 = float(d["x2"])
            det.y2 = float(d["y2"])
            det.center_x = float((d["x1"] + d["x2"]) / 2.0)
            det.center_y = float((d["y1"] + d["y2"]) / 2.0)
            det.class_name = str(d.get("class_name", "unknown"))
            det.confidence = float(d.get("confidence", 0.0))
            det.bbox_area_px = float(d.get("area", 0.0))
            out.detections.append(det)

        self._pub.publish(out)

    def _publish_empty(self, frame_id: str, frame_number: int,
                       signal_ok: bool, mean: float, std: float,
                       latency_ms: float) -> None:
        out = DetectionArray()
        now = self.get_clock().now()
        out.frame_timestamp = self._ros_time(now)
        out.camera_id = self._camera_id
        out.frame_id = frame_id
        out.frame_number = frame_number
        out.signal_ok = signal_ok
        out.signal_mean_luma = float(mean)
        out.signal_std_luma = float(std)
        out.stage1_latency_ms = float(latency_ms)
        out.detections = []
        self._pub.publish(out)

    @staticmethod
    def _ros_time(stamp) -> RosTime:
        ros_t = RosTime()
        t_ns = stamp.nanoseconds
        ros_t.sec = int(t_ns // 1_000_000_000)
        ros_t.nanosec = int(t_ns % 1_000_000_000)
        return ros_t


def main(args=None) -> None:
    rclpy.init(args=args)
    node = FwInferenceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
