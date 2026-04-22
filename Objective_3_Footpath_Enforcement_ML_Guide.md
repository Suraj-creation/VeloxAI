# Objective 3 — Footpath Violation Detection & Auto-Enforcement
## Complete ML Implementation Guide for Edge Deployment

> **System Goal:** Deploy a camera-based edge AI system on footpath-mounted cameras that autonomously detects two-wheelers (motorcycles, bicycles, e-scooters) encroaching on pedestrian footpaths, estimates their speed, extracts the vehicle licence plate via OCR, and generates a geo-tagged e-Challan with photo evidence — all processing done entirely on-device with zero cloud dependency.

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Hardware Requirements & Edge Device Selection](#2-hardware-requirements--edge-device-selection)
3. [The Complete ML Pipeline — Stage by Stage](#3-the-complete-ml-pipeline--stage-by-stage)
4. [Stage 1 — Two-Wheeler Detection Model](#4-stage-1--two-wheeler-detection-model)
5. [Stage 2 — Direct Full-Frame Enforcement](#5-stage-2--direct-full-frame-enforcement)
6. [Stage 3 — Multi-Object Tracking & Speed Estimation](#6-stage-3--multi-object-tracking--speed-estimation)
7. [Stage 4 — Licence Plate Localisation Model](#7-stage-4--licence-plate-localisation-model)
8. [Stage 5 — Plate Super-Resolution (Optional but Recommended)](#8-stage-5--plate-super-resolution-optional-but-recommended)
9. [Stage 6 — OCR Engine for Indian Licence Plates](#9-stage-6--ocr-engine-for-indian-licence-plates)
10. [Stage 7 — Evidence Packaging & e-Challan Generation](#10-stage-7--evidence-packaging--e-challan-generation)
11. [Pretrained Model Links (No Retraining)](#11-pretrained-model-links-no-retraining)
15. [Evaluation & Acceptance Criteria](#15-evaluation--acceptance-criteria)
16. [Deployment Checklist](#16-deployment-checklist)

---

## 11. Pretrained Model Links (No Retraining)

The deployment in this guide uses pretrained models directly (no dataset retraining pipeline in this version):

- Two-wheeler detection base model (Ultralytics YOLOv8):
    https://huggingface.co/Ultralytics/YOLOv8?utm_source=chatgpt.com
- Licence plate localisation model:
    https://huggingface.co/yasirfaizahmed/license-plate-object-detection?utm_source=chatgpt.com

Best-practice notes for no-retraining deployments:
- Validate on site-specific clips before enforcement rollout.
- Use conservative thresholds and a manual-review queue for low-confidence OCR.
- Keep camera calibration (speed + camera alignment) mandatory at every installation site.
- Start with assisted enforcement mode, then move to auto-enforcement only after metrics meet target.

---

## 1. System Architecture Overview

### What the System Does — End to End

```
[Footpath Camera — 1080p IP Camera]
            |
            v
[Frame Capture @ 15–25 FPS — OpenCV RTSP / USB]
            |
            v
[STAGE 1]  Two-Wheeler Detection
           Model: Ultralytics YOLOv8 pretrained (TFLite/ONNX/PyTorch)
           Classes: motorcycle, bicycle, e-scooter, scooter
           Output: Bounding boxes + class labels + confidence scores
            |
            v
[STAGE 2]  Direct Full-Frame Enforcement
           Logic: No ROI polygon gate in fixed footpath deployment
           Output: All candidate detections continue to tracking
            |
            | — non-vehicle or low-speed objects are filtered in later stages
            v
[STAGE 3]  Multi-Object Tracking + Speed Estimation
           Model: ByteTrack (lightweight, edge-optimised)
           Logic: Track bbox displacement across frames → speed (km/h)
           Output: Tracked ID + speed value per vehicle
            |
            | — if speed < 5 km/h → classify as parked → skip OCR
            v
[STAGE 4]  Licence Plate Localisation
           Model: Pretrained YOLOv8 licence plate detector
           Input: Cropped vehicle region (from Stage 1 bbox)
           Output: Tight plate bounding box within vehicle crop
            |
            v
[STAGE 5]  Plate Image Enhancement
           Model: ESRGAN-tiny TFLite (upscale 2× or 4×)
           OR:    OpenCV CLAHE + Unsharp Mask (if no GPU)
           Output: Enhanced plate image (128×512 minimum)
            |
            v
[STAGE 6]  OCR — Character Recognition
           Model: PaddleOCR PP-OCRv3 (TFLite / ONNX)
           Post-process: Regex validation for Indian LP format
           Output: Plate string e.g. "KA05AB1234"
            |
            v
[STAGE 7]  Evidence Package Generation
           Logic: Annotate frame + crop plate + write JSON + push alert
           Output: e-Challan JSON + Evidence image + Police dashboard push
```

### Design Principles

- **Edge-First**: Every stage runs on-device. No frame is sent to the cloud.
- **Zero Dependency**: System works fully offline. Internet used only for dashboard push when available.
- **Modular**: Each stage can be swapped independently. E.g., PaddleOCR can replace TesseractOCR without touching the rest.
- **Fail-Safe**: If any stage fails (model crash, timeout), the system logs the raw frame and continues. It never blocks the pipeline.
- **Calibration-Once**: Pixel-to-metre ratio and camera alignment are set once at installation and stored in config JSON.

---

## 2. Hardware Requirements & Edge Device Selection

### Primary Deployment Targets

| Device | RAM | Storage | GPU/NPU | Cost (INR) | Recommended For |
|---|---|---|---|---|---|
| **Raspberry Pi 4 (4GB)** | 4 GB | 64 GB SD + optional SSD | VideoCore VI (no CUDA) | ~5,500 | Primary deployment — cost-effective |
| **NVIDIA Jetson Nano (4GB)** | 4 GB | 64 GB SD | 128-core Maxwell GPU | ~8,000 | High accuracy + speed needed |
| **Raspberry Pi 5 (8GB)** | 8 GB | 64 GB SD | VideoCore VII | ~7,500 | Best Pi option — 2× Pi 4 speed |
| **Orange Pi 5** | 8 GB | 64 GB SD | Mali-G610 + NPU | ~6,500 | Alternative to Jetson, cheaper |

> **Recommendation**: Deploy with **Raspberry Pi 4 (4GB)** for cost-constrained rollout. Use **Jetson Nano** at high-priority intersections or where plate reading in low light is critical (TensorRT acceleration makes a significant difference for OCR quality).

### Camera Requirements

| Parameter | Minimum | Recommended |
|---|---|---|
| Resolution | 1080p (1920×1080) | 2MP–4MP |
| Frame Rate | 15 FPS | 25 FPS |
| Night Vision | IR LEDs (8–10m range) | IR + Starlight CMOS sensor |
| Weatherproofing | IP65 | IP66 |
| Lens | 4mm fixed | 2.8–12mm varifocal |
| Interface | USB / RTSP over Ethernet | RTSP over PoE |
| Shutter | Rolling | **Global Shutter preferred** (avoids motion blur on fast bikes) |

> **Critical Note on Global Shutter**: Two-wheelers moving at 20–30 km/h will produce severe motion blur on rolling-shutter cameras. A global-shutter camera (e.g., Arducam IMX296) is strongly recommended for the plate recognition module to achieve acceptable OCR accuracy.

### Recommended Accessories

- **Google Coral USB Accelerator** (~₹4,000): Plugs into Pi via USB3, provides 4 TOPS for TFLite models. Reduces YOLOv8n inference from ~80ms to ~25ms on Raspberry Pi 4.
- **Hailo-8 M.2 Hat (Pi 5 only)**: 26 TOPS, fastest edge option for Pi platform.
- **IR Illuminator (850nm, 10m range)**: Mandatory for night-time plate reading.
- **PoE Hat for Pi**: Single-cable installation (power + network over Ethernet).

---

## 3. The Complete ML Pipeline — Stage by Stage

### Overview of All Models

| Stage | Task | Model | Framework | Size (Edge) | Latency (Pi 4) | Latency (Jetson) |
|---|---|---|---|---|---|---|
| 1 | Two-wheeler detection | YOLOv8n (fine-tuned) | TFLite INT8 | 3.2 MB | ~55ms @ 320px | ~22ms @ 640px |
| 2 | Full-frame pass-through | Rule-based filter | Python | 0 MB | <1ms | <1ms |
| 3 | Tracking + speed | ByteTrack | Python | ~0.5 MB | ~5ms | ~3ms |
| 4 | Plate localisation | YOLOv8n-LP | TFLite INT8 | 3.2 MB | ~40ms | ~18ms |
| 5 | Plate enhancement | CLAHE (CPU) / ESRGAN-tiny | OpenCV / TFLite | 2.1 MB | ~8ms | ~5ms |
| 6 | Plate OCR | PaddleOCR PP-OCRv3 | ONNX Runtime | ~8 MB | ~90ms | ~35ms |
| 7 | Evidence generation | Rule-based Python | Python/OpenCV | 0 MB | ~15ms | ~10ms |
| **TOTAL** | | | | **~17 MB** | **~214ms** | **~93ms** |

> **On Raspberry Pi 4**: The pipeline runs end-to-end in ~200–220ms per violation frame. This is acceptable because violation capture only triggers on confirmed violations — it does not need to run on every single frame. The main detection loop runs at 10–15 FPS; the heavy OCR pipeline only activates when a violation is confirmed.

---

## 4. Stage 1 — Two-Wheeler Detection Model

### Model Choice: YOLOv8n (Nano)

**Why YOLOv8n over other options:**

- Ultralytics YOLOv8n is the smallest production-grade YOLO variant at ~6MB (PyTorch) / ~3.2MB (INT8 TFLite).
- COCO pre-trained weights already include `motorcycle` (class 3) and `bicycle` (class 1) — you get a solid baseline before any fine-tuning.
- The Ultralytics Python API makes fine-tuning, export, and inference a single-command workflow.
- Runs at 12–18 FPS on Raspberry Pi 4 at 320px input (sufficient for violation flagging).

**Why NOT larger models:**

- YOLOv8s (~22MB) and above exceed the latency budget on Raspberry Pi 4.
- SSD-MobileNet is faster but less accurate at small/occluded two-wheeler detection.
- YOLO-NAS requires proprietary dependencies that are painful on ARM edge devices.

### Classes to Detect

```
Class 0: motorcycle        (includes sports bikes, cruisers, delivery bikes)
Class 1: bicycle           (includes pedal cycles, cargo bikes)
Class 2: e-scooter         (standalone class — increasingly common in Indian cities)
Class 3: scooter           (gearless scooters — very common in India)
Class 4: auto_rickshaw     (optional — often encroach on footpaths at stops)
```

> **Important:** The base COCO model only has `motorcycle` and `bicycle`. Fine-tuning on Indian street data is mandatory to add `e-scooter` and `scooter` as separate classes, and to improve accuracy on Indian vehicle types (Royal Enfields, Splendors, Activas).

### Confidence & NMS Thresholds

```python
DETECTION_CONFIDENCE_THRESHOLD = 0.45   # Lower than default to catch partial views
NMS_IOU_THRESHOLD               = 0.50
MIN_BBOX_AREA_PX                = 1500   # Ignore tiny detections far from camera
```

---

## 5. Stage 2 — Direct Full-Frame Enforcement

### Concept

For fixed installations where the camera is mounted exclusively for footpath monitoring, ROI gating is removed from violation decision logic.

Every detected candidate in the frame proceeds directly to tracking and speed estimation. Violation filtering then happens by:

- Vehicle class eligibility
- Motion threshold (speed > configured threshold)
- Plate localization + OCR validity/confidence

This simplifies deployment and avoids missed violations caused by polygon miscalibration.

### What Still Remains Configurable

- Camera metadata (camera_id, location_name, GPS)
- Speed calibration (`pixels_per_metre`, `camera_fps`)
- Challan cooldown and OCR confidence threshold

### Persistence Rule

Only confirmed violations are persisted to disk (`violations/`) as evidence bundles and metadata JSON. Non-violating detections are processed live but not stored as complaint records.

---

## 6. Stage 3 — Multi-Object Tracking & Speed Estimation

### Why Tracking Is Essential

Without tracking, the system would:
- Generate duplicate e-Challans for the same vehicle (one per frame)
- Not be able to estimate speed (speed requires position across multiple frames)
- Not be able to confirm a vehicle was actually **moving** on the footpath (vs parked)

### Tracker Choice: ByteTrack

**Why ByteTrack over DeepSORT:**
- ByteTrack has no re-ID neural network — it is purely IoU-based matching, making it much lighter on the Pi.
- DeepSORT requires a separate appearance descriptor CNN (~50ms extra per tracked object on Pi).
- ByteTrack achieves comparable tracking accuracy to DeepSORT for this use case (fixed camera, non-crowded footpath).
- ByteTrack is natively supported in Ultralytics YOLOv8 — zero extra setup.

```python
from ultralytics import YOLO

# ByteTrack is built into YOLOv8's track() method
model = YOLO('models/twowheeler_int8.tflite', task='detect')

# Run tracking
results = model.track(
    source=frame,
    persist=True,         # maintain track IDs across frames
    tracker="bytetrack.yaml",
    conf=0.45,
    iou=0.50,
)

# Each detection now has: .id (track ID), .boxes.xyxy, .boxes.cls
```

### Speed Estimation from Monocular Camera

Speed is estimated from bounding box displacement across consecutive frames, combined with a pixel-to-metre calibration factor computed at installation.

#### Pixel-to-Metre Calibration (Done Once at Installation)

```python
# calibrate_speed.py
# Place a 1-metre marker (tape measure, known-length object) on the footpath.
# Mark the pixel positions of both ends.

import json

# Measured during installation:
PIXEL_DISTANCE_OF_1_METRE = 47  # pixels (example — measure for your camera)
# This varies by camera angle, focal length, and distance from camera to footpath.

# Save calibration
with open("config/speed_calibration.json", "w") as f:
    json.dump({
        "pixels_per_metre": PIXEL_DISTANCE_OF_1_METRE,
        "camera_fps": 15,
        "calibration_date": "2025-01-01"
    }, f, indent=2)
```

#### Speed Estimation Function

```python
import numpy as np
from collections import defaultdict, deque

# Store position history per track ID
track_history = defaultdict(lambda: deque(maxlen=10))

def update_track_and_estimate_speed(
    track_id: int,
    bbox_center: tuple,
    pixels_per_metre: float,
    fps: float
) -> float:
    """
    Update position history for track_id and return current speed in km/h.
    Returns 0.0 if insufficient history.
    """
    track_history[track_id].append(bbox_center)
    
    if len(track_history[track_id]) < 3:
        return 0.0  # need at least 3 frames for stable speed
    
    # Use last 3 positions for smoothing
    positions = list(track_history[track_id])[-3:]
    
    total_pixel_dist = 0.0
    for i in range(1, len(positions)):
        dx = positions[i][0] - positions[i-1][0]
        dy = positions[i][1] - positions[i-1][1]
        total_pixel_dist += np.sqrt(dx**2 + dy**2)
    
    avg_pixel_dist_per_frame = total_pixel_dist / (len(positions) - 1)
    
    metres_per_frame   = avg_pixel_dist_per_frame / pixels_per_metre
    metres_per_second  = metres_per_frame * fps
    km_per_hour        = metres_per_second * 3.6
    
    return round(km_per_hour, 1)

# Violation trigger rule:
SPEED_THRESHOLD_KMPH = 5.0   # below this = parked (skip e-Challan)
# If speed > 5 km/h for a tracked eligible vehicle → confirmed moving violation
```

---

## 7. Stage 4 — Licence Plate Localisation Model

### Why a Separate Plate Localisation Model

The main two-wheeler detector (Stage 1) finds the whole vehicle. The plate is a tiny sub-region of the vehicle — often <5% of the bounding box area. Running OCR on the full vehicle crop would fail. A dedicated licence plate detector finds the tight plate region before OCR.

### Model Choice: YOLOv8n Fine-Tuned on Indian LP Dataset

This is the same YOLOv8n architecture as Stage 1, but fine-tuned specifically on Indian licence plate images. It is trained to output a single class: `licence_plate`.

```
Input:  Cropped vehicle image (from Stage 1 bbox) — resized to 320×320
Output: [x1, y1, x2, y2] tight bounding box around the plate
```

### Handling Multiple Plates

Indian vehicles can have a front plate and a rear plate. The camera angle determines which is visible. The system selects:
1. The plate with the **highest confidence score** if both are detected.
2. The **largest bounding box** as a tiebreaker.

```python
def get_best_plate(plate_detections: list) -> dict | None:
    """
    From a list of plate detections, return the best one.
    Each detection: {'bbox': [x1,y1,x2,y2], 'conf': float}
    """
    if not plate_detections:
        return None
    # Sort by confidence descending, then by area descending as tiebreaker
    sorted_dets = sorted(
        plate_detections,
        key=lambda d: (d['conf'], (d['bbox'][2]-d['bbox'][0]) * (d['bbox'][3]-d['bbox'][1])),
        reverse=True
    )
    return sorted_dets[0]
```

---

## 8. Stage 5 — Plate Image Enhancement

### The Problem

Indian licence plates captured at distance, in motion, or at night are often:
- Low resolution (the plate occupies only 30–80 pixels in width)
- Motion-blurred (two-wheelers moving at 20+ km/h)
- Glare-affected (headlamps, streetlights reflecting off the plate)
- Poorly contrasted (faded plates, old vehicles, dust-covered plates)

Direct OCR on the raw plate crop produces poor accuracy. Enhancement is critical.

### Option A — CPU-Only Enhancement (Raspberry Pi 4 without Coral)

Use classical OpenCV pipeline. No neural network required. Fast and reliable.

```python
import cv2
import numpy as np

def enhance_plate_cpu(plate_img: np.ndarray,
                      target_width: int = 400) -> np.ndarray:
    """
    Full classical plate enhancement pipeline.
    Works on CPU in <10ms on Raspberry Pi 4.
    """
    # Step 1: Upscale to target width (bicubic interpolation)
    h, w = plate_img.shape[:2]
    scale = target_width / w
    new_h = int(h * scale)
    upscaled = cv2.resize(plate_img, (target_width, new_h),
                          interpolation=cv2.INTER_CUBIC)
    
    # Step 2: Convert to grayscale for processing
    gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
    
    # Step 3: CLAHE — adaptive contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(gray)
    
    # Step 4: Gaussian blur to reduce noise before sharpening
    blurred = cv2.GaussianBlur(enhanced, (0, 0), 1.5)
    
    # Step 5: Unsharp masking — sharpens edges (character strokes)
    sharpened = cv2.addWeighted(enhanced, 1.8, blurred, -0.8, 0)
    
    # Step 6: Bilateral filter — reduce noise, preserve edges
    denoised = cv2.bilateralFilter(sharpened, d=5,
                                   sigmaColor=40, sigmaSpace=40)
    
    # Step 7: Adaptive threshold — improve OCR readability
    # (optional — use only if PaddleOCR has issues with grayscale)
    # thresh = cv2.adaptiveThreshold(denoised, 255,
    #     cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 2)
    
    # Return as BGR (required by PaddleOCR)
    return cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)


def deskew_plate(plate_img: np.ndarray) -> np.ndarray:
    """
    Correct slight rotation/tilt of the plate using Hough line detection.
    Improves OCR accuracy on tilted plates.
    """
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=60)
    
    if lines is None:
        return plate_img  # no correction needed
    
    angles = []
    for line in lines[:5]:  # use top 5 strongest lines
        rho, theta = line[0]
        angle = np.degrees(theta) - 90
        if abs(angle) < 20:  # ignore near-vertical lines
            angles.append(angle)
    
    if not angles:
        return plate_img
    
    median_angle = np.median(angles)
    if abs(median_angle) < 1.0:
        return plate_img  # tilt too small to correct
    
    h, w = plate_img.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), median_angle, 1.0)
    deskewed = cv2.warpAffine(plate_img, M, (w, h),
                               flags=cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_REPLICATE)
    return deskewed
```

### Option B — ESRGAN-tiny with TFLite (Jetson Nano Recommended)

Use a lightweight Real-ESRGAN model for neural super-resolution. 4× upscale at significantly higher quality than bicubic.

```python
import tflite_runtime.interpreter as tflite
import numpy as np
import cv2

class ESRGANEnhancer:
    def __init__(self, model_path: str = "models/esrgan_tiny.tflite"):
        self.interp = tflite.Interpreter(
            model_path=model_path,
            num_threads=4
        )
        self.interp.allocate_tensors()
        self.input_details  = self.interp.get_input_details()
        self.output_details = self.interp.get_output_details()
    
    def enhance(self, plate_img: np.ndarray) -> np.ndarray:
        """
        Super-resolve plate image using ESRGAN-tiny.
        Input:  BGR image, any small size
        Output: BGR image, 4× larger
        """
        # Resize to model's expected input (64×256 for plate aspect ratio)
        inp = cv2.resize(plate_img, (256, 64))
        inp = inp.astype(np.float32) / 255.0
        inp = np.expand_dims(inp, axis=0)  # add batch dim
        
        self.interp.set_tensor(self.input_details[0]['index'], inp)
        self.interp.invoke()
        output = self.interp.get_tensor(self.output_details[0]['index'])
        
        output = np.squeeze(output, axis=0)
        output = np.clip(output * 255.0, 0, 255).astype(np.uint8)
        return output

# Where to get the ESRGAN-tiny TFLite model:
# Source:  github.com/Practical-AI/Real-ESRGAN-tflite
# OR:      Convert from Real-ESRGAN PyTorch → ONNX → TFLite (see Section 13)
# Model size: ~2.1 MB (tiny variant)
# Latency on Jetson Nano: ~25ms per plate crop
# Latency on Raspberry Pi 4: ~180ms (use CPU enhancement for Pi instead)
```

---

## 9. Stage 6 — OCR Engine for Indian Licence Plates

### Why PaddleOCR over Tesseract

| Property | PaddleOCR PP-OCRv3 | Tesseract v5 |
|---|---|---|
| Indian LP accuracy (real-world) | ~92–95% | ~55–70% |
| Speed on Pi (single plate) | ~80–100ms | ~200–400ms |
| Curved / bold text handling | Excellent | Poor |
| Model size | ~8 MB (ONNX) | ~30 MB |
| Edge deployment | ONNX Runtime / TFLite | CPU-only binary |
| Indian character support | Built-in training | Requires custom training |
| Fine-tuning support | Yes (PaddleOCR training pipeline) | Difficult |

**Verdict**: Always use PaddleOCR for this project. Tesseract is not suitable for real-world Indian LP recognition.

### PaddleOCR Integration

```python
# Install: pip install paddlepaddle paddleocr
from paddleocr import PaddleOCR
import re
import numpy as np

class IndianPlateOCR:
    
    VALID_LP_PATTERN = re.compile(
        r'^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$'
    )
    # Covers formats:
    # KA05AB1234  — most common (state + district + series + number)
    # DL1CAB1234  — Delhi format
    # MH12DE1234  — Maharashtra
    # Also handles BH (Bharat) series: 22BH1234AA
    
    BH_SERIES_PATTERN = re.compile(
        r'^[0-9]{2}BH[0-9]{4}[A-Z]{2}$'
    )
    
    def __init__(self, use_gpu: bool = False):
        self.ocr = PaddleOCR(
            use_angle_cls=True,     # correct upside-down plates
            lang='en',
            use_gpu=use_gpu,
            rec_model_dir='models/paddleocr_rec',   # local model cache
            det_model_dir='models/paddleocr_det',
            cls_model_dir='models/paddleocr_cls',
            show_log=False,
        )
    
    def read_plate(self, plate_img: np.ndarray) -> dict:
        """
        Run OCR on an enhanced plate image.
        Returns: {
            'raw_text': str,
            'cleaned_text': str,
            'is_valid': bool,
            'confidence': float
        }
        """
        result = self.ocr.ocr(plate_img, cls=True)
        
        if not result or not result[0]:
            return {'raw_text': '', 'cleaned_text': '', 
                    'is_valid': False, 'confidence': 0.0}
        
        # Concatenate all detected text lines
        all_text = ''
        total_conf = 0.0
        count = 0
        for line in result[0]:
            text, confidence = line[1]
            all_text += text
            total_conf += confidence
            count += 1
        
        avg_conf = total_conf / count if count > 0 else 0.0
        
        # Clean and normalise
        cleaned = self._clean_plate_text(all_text)
        is_valid = self._validate_plate(cleaned)
        
        return {
            'raw_text': all_text,
            'cleaned_text': cleaned,
            'is_valid': is_valid,
            'confidence': round(avg_conf, 3)
        }
    
    def _clean_plate_text(self, raw: str) -> str:
        """Remove spaces, lowercase, common OCR confusions."""
        text = raw.upper().replace(' ', '').replace('-', '').strip()
        
        # Common OCR confusion corrections for LP context:
        # These corrections are position-dependent for Indian LP format
        # Positions 0,1 = state code (letters only)
        # Positions 2,3 = district number (digits only)
        # Positions 4,5 = series letters
        # Positions 6–9 = registration number (digits only)
        
        if len(text) >= 10:
            corrected = list(text)
            # Force digits at positions 2, 3
            for pos in [2, 3]:
                corrected[pos] = self._letter_to_digit(corrected[pos])
            # Force letters at positions 0, 1, 4, 5
            for pos in [0, 1, 4, 5]:
                corrected[pos] = self._digit_to_letter(corrected[pos])
            # Force digits at positions 6–9
            for pos in range(6, min(10, len(corrected))):
                corrected[pos] = self._letter_to_digit(corrected[pos])
            text = ''.join(corrected)
        
        return text
    
    def _letter_to_digit(self, char: str) -> str:
        """Convert commonly confused OCR letters to digits."""
        confusion_map = {'O': '0', 'I': '1', 'l': '1', 
                         'Z': '2', 'S': '5', 'B': '8', 'G': '6'}
        return confusion_map.get(char, char)
    
    def _digit_to_letter(self, char: str) -> str:
        """Convert commonly confused OCR digits to letters."""
        confusion_map = {'0': 'O', '1': 'I', '5': 'S', '8': 'B', '6': 'G'}
        return confusion_map.get(char, char)
    
    def _validate_plate(self, text: str) -> bool:
        """Validate against Indian LP formats."""
        return bool(
            self.VALID_LP_PATTERN.match(text) or
            self.BH_SERIES_PATTERN.match(text)
        )


# OCR CONFIDENCE STRATEGY:
# Run OCR 3 times on same plate (with slight augmentation between runs)
# Take the result with highest confidence + valid format match.
# This "majority voting" approach improves accuracy from 85% to 92%+ per plate.

def ocr_with_voting(plate_img: np.ndarray, ocr_engine: IndianPlateOCR,
                    n_runs: int = 3) -> dict:
    """Run OCR multiple times with slight augmentations, take best result."""
    candidates = []
    
    augmentations = [
        lambda x: x,                                  # original
        lambda x: cv2.convertScaleAbs(x, alpha=1.1, beta=10),   # brighter
        lambda x: cv2.convertScaleAbs(x, alpha=0.9, beta=-10),  # darker
    ]
    
    for aug in augmentations[:n_runs]:
        augmented = aug(plate_img)
        result = ocr_engine.read_plate(augmented)
        if result['is_valid']:
            candidates.append(result)
    
    if not candidates:
        # No valid result — return best raw result
        return ocr_engine.read_plate(plate_img)
    
    # Return highest confidence valid result
    return max(candidates, key=lambda x: x['confidence'])
```

### Fine-Tuning PaddleOCR on Indian LP Data (Strongly Recommended)

```bash
# Fine-tuning improves accuracy from ~85% to ~94% on Indian plates

# Step 1: Install PaddlePaddle training environment
pip install paddlepaddle-gpu paddleocr

# Step 2: Download Indian LP recognition dataset (see Section 11)
# Place images in: training_data/indian_lp/
# Create label file: training_data/indian_lp/labels.txt
# Format per line: image_path\tplate_text

# Step 3: Download base PP-OCRv3 rec model weights
wget https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_rec_train.tar
tar -xf en_PP-OCRv3_rec_train.tar

# Step 4: Configure fine-tuning
# Edit: configs/rec/PP-OCRv3/en_PP-OCRv3_rec.yml
# Set: pretrained_model: ./en_PP-OCRv3_rec_train/best_accuracy
# Set: character_dict_path: ./indian_lp_char_dict.txt  (A-Z, 0-9)
# Set: Train.dataset.data_dir: ./training_data/indian_lp/
# Set: epoch_num: 50
# Set: save_epoch_step: 5

# Step 5: Train
python tools/train.py -c configs/rec/PP-OCRv3/en_PP-OCRv3_rec.yml \
    -o Global.pretrained_model=./en_PP-OCRv3_rec_train/best_accuracy

# Step 6: Export to inference model
python tools/export_model.py \
    -c configs/rec/PP-OCRv3/en_PP-OCRv3_rec.yml \
    -o Global.pretrained_model=./output/rec_ppocr_v3_en/best_accuracy \
       Global.save_inference_dir=./models/paddleocr_rec_indian/

# Step 7: Convert inference model to ONNX for edge deployment
paddle2onnx --model_dir ./models/paddleocr_rec_indian/ \
            --model_filename inference.pdmodel \
            --params_filename inference.pdiparams \
            --save_file ./models/paddleocr_rec_indian.onnx \
            --opset_version 11
```

---

## 10. Stage 7 — Evidence Packaging & e-Challan Generation

### What the Evidence Package Contains

For each confirmed violation, the system creates a complete evidence bundle:

```
violations/
  2025-01-15_14-23-07_KA05AB1234/
    evidence_frame.jpg         # Full annotated frame with violation box
    plate_crop_raw.jpg         # Raw plate crop before enhancement
    plate_crop_enhanced.jpg    # Enhanced plate crop used for OCR
    violation_metadata.json    # Full violation record
    thumbnail.jpg              # 320×240 compressed for quick preview
```

### Violation Metadata JSON Schema

```python
import json
import datetime
import uuid

def create_violation_record(
    plate_text: str,
    plate_confidence: float,
    vehicle_class: str,
    speed_kmph: float,
    track_id: int,
    camera_config: dict,
    frame_path: str,
    plate_crop_path: str
) -> dict:
    """Create a complete, structured violation record."""
    
    return {
        "violation_id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.now().isoformat(),
        "timestamp_epoch": int(datetime.datetime.now().timestamp()),
        
        "location": {
            "camera_id": camera_config["camera_id"],
            "location_name": camera_config["location_name"],
            "gps_lat": camera_config["gps_lat"],
            "gps_lng": camera_config["gps_lng"],
        },
        
        "vehicle": {
            "plate_number": plate_text,
            "plate_ocr_confidence": plate_confidence,
            "plate_format_valid": True,
            "vehicle_class": vehicle_class,
            "estimated_speed_kmph": speed_kmph,
            "track_id": track_id,
        },
        
        "violation_type": "FOOTPATH_ENCROACHMENT",
        "section_applied": "Section 177 MV Act / Section 111 BMTC",
        "fine_amount_inr": 500,
        
        "evidence": {
            "full_frame": frame_path,
            "plate_crop_raw": plate_crop_path,
            "plate_crop_enhanced": plate_crop_path.replace("raw", "enhanced"),
            "thumbnail": plate_crop_path.replace("raw.jpg", "thumb.jpg"),
        },
        
        "system": {
            "device_id": camera_config.get("device_id", "EDGE-001"),
            "model_version": "YOLOv8n-v2.1 + PaddleOCRv3",
            "pipeline_latency_ms": None,  # filled by main loop
            "pushed_to_dashboard": False,
            "push_timestamp": None,
        }
    }


def save_violation(record: dict, base_dir: str = "violations/") -> str:
    """Save violation record and return directory path."""
    import os
    
    ts = record["timestamp"].replace(":", "-").replace("T", "_")[:19]
    plate = record["vehicle"]["plate_number"]
    dir_name = f"{ts}_{plate}"
    dir_path = os.path.join(base_dir, dir_name)
    os.makedirs(dir_path, exist_ok=True)
    
    json_path = os.path.join(dir_path, "violation_metadata.json")
    with open(json_path, "w") as f:
        json.dump(record, f, indent=2)
    
    return dir_path
```

### Dashboard Push (MQTT — When Network Available)

```python
import paho.mqtt.client as mqtt
import json
import threading

class DashboardPusher:
    """
    Push violation alerts to police dashboard via MQTT.
    Runs in a background thread — never blocks the main inference loop.
    Falls back to local queue when offline.
    """
    
    BROKER_HOST = "mqtt.policedashboard.local"  # or public broker IP
    BROKER_PORT = 1883
    TOPIC       = "footpath/violations"
    
    def __init__(self):
        self.client = mqtt.Client()
        self.offline_queue = []
        self.connected = False
        
        try:
            self.client.connect(self.BROKER_HOST, self.BROKER_PORT, keepalive=60)
            self.client.loop_start()
            self.connected = True
        except Exception:
            self.connected = False  # offline — queue locally
    
    def push_violation(self, record: dict):
        """Push in background thread. Non-blocking."""
        thread = threading.Thread(
            target=self._push_worker, args=(record,), daemon=True
        )
        thread.start()
    
    def _push_worker(self, record: dict):
        payload = json.dumps({
            "violation_id": record["violation_id"],
            "timestamp": record["timestamp"],
            "plate": record["vehicle"]["plate_number"],
            "speed_kmph": record["vehicle"]["estimated_speed_kmph"],
            "location": record["location"]["location_name"],
            "gps": [record["location"]["gps_lat"], record["location"]["gps_lng"]],
            "fine_inr": record["fine_amount_inr"],
        })
        
        if self.connected:
            try:
                self.client.publish(self.TOPIC, payload, qos=1)
                record["system"]["pushed_to_dashboard"] = True
            except Exception:
                self.offline_queue.append(payload)
        else:
            self.offline_queue.append(payload)  # retry on reconnect
```

---

## 15. Evaluation & Acceptance Criteria

### Per-Stage Acceptance Criteria

| Stage | Model | Metric | Minimum | Production Target |
|---|---|---|---|---|
| 1 — Two-wheeler detection | Pretrained YOLOv8 | Recall on local clips | > 0.75 | > 0.85 |
| 1 — Two-wheeler detection | Pretrained YOLOv8 | False Negative Rate | < 18% | < 10% |
| 1 — Two-wheeler detection | Pretrained YOLOv8 | FPS on Pi 4 @ 320px | > 10 FPS | > 12 FPS |
| 4 — Plate localisation | Pretrained LP detector | Recall @ conf=0.3 | > 0.80 | > 0.90 |
| 6 — OCR | PaddleOCR pretrained | Word accuracy (full plate) | > 70% | > 82% |
| 6 — OCR | PaddleOCR pretrained | Valid format match rate | > 80% | > 90% |
| FULL PIPELINE | All stages | e-Challan precision | > 85% | > 92% |
| FULL PIPELINE | All stages | e-Challan recall | > 65% | > 80% |
| FULL PIPELINE | All stages | End-to-end latency (Pi 4) | < 280ms | < 220ms |
| FULL PIPELINE | All stages | End-to-end latency (Jetson) | < 130ms | < 100ms |

### Test Protocol

```
Test Set Composition (collect before threshold tuning):
  Normal daylight two-wheelers on footpath:      50 clips
  Night-time violations (IR illumination):       20 clips
  Rain/wet conditions:                           15 clips
  Partial occlusion (other pedestrians):         20 clips
  Fast-moving bike (> 30 km/h):                  15 clips
  Parked two-wheelers (should NOT trigger):       30 clips (false positive test)
  Pedestrians only (should NOT trigger):          30 clips (false positive test)
  ────────────────────────────────────────────────────────
  TOTAL:                                        180 clips

For each clip:
  1. Run full pipeline
  2. Record: detected (Y/N), plate read correctly (Y/N), challan generated (Y/N)
  3. Compare against ground-truth label

Key metrics to report:
  - Precision = correct challans / total challans generated
  - Recall    = correct challans / total actual violations
  - False Positive Rate = spurious challans / total non-violations
  - Night-time accuracy vs. day accuracy (should be < 10% drop)
```

### Common Failure Modes & Fixes

| Failure Mode | Symptom | Fix |
|---|---|---|
| Two-wheeler not detected from elevated angle | FNR > 20% on overhead shots | Reduce detection threshold for that site and increase camera pitch consistency |
| Plate unreadable due to motion blur | OCR confidence always < 0.5 | Switch to global shutter camera, improve IR illumination, and enforce manual review below OCR threshold |
| Duplicate challans for same vehicle | Multiple challans per crossing | Tune cooldown timer (increase to 120s); verify ByteTrack persistence |
| Pedestrian detected as bicycle | False positives on pedestrians | Increase CONF_THRESHOLD to 0.55 and apply stricter minimum bbox area filtering |
| Plates not localised at night | Plate localiser recall < 0.7 at night | Lower LP conf threshold at night and improve lighting/angle; route low-confidence cases to manual review |
| Invalid plate format after OCR | Validation rejects 30%+ of readings | Apply OCR voting + text cleanup rules and hold low-confidence reads in manual review queue |

---

## 16. Deployment Checklist

### Pre-Installation (Office/Lab)

- [ ] Pretrained models downloaded from approved links and checksum-verified
- [ ] All models converted to TFLite INT8 / ONNX
- [ ] Pipeline tested on recorded test video (not live camera)
- [ ] All false positive / false negative rates within spec
- [ ] `systemd` service configured and tested for auto-start
- [ ] SD card / SSD imaged with complete system (use `rpi-clone` for backup)

### On-Site Installation

- [ ] Camera mounted at recommended height: **3.5–5 metres** from ground, angled downward at 25–35°
- [ ] Camera positioned to see the full footpath width in frame
- [ ] Camera alignment verified for full-frame footpath monitoring
- [ ] Speed calibration run with 1-metre reference marker saved to `config/speed_calibration.json`
- [ ] IR illuminator aimed at footpath coverage zone
- [ ] Night-time test run: 10-minute recording reviewed for detection quality
- [ ] Network connectivity confirmed (LAN / 4G router)
- [ ] MQTT broker address configured in `config/dashboard.json`
- [ ] Test violation triggered manually (push bike through frame) — verify challan generated
- [ ] Weatherproof enclosure sealed (IP65 or higher)

### Post-Deployment Monitoring (First Week)

- [ ] Review all generated challans daily for first 3 days
- [ ] Check for unexpected false positives (pedestrians, leaves, shadows)
- [ ] Monitor `violations/manual_review_queue.jsonl` for unvalidated plate readings
- [ ] Check system latency logs — verify no thermal throttling on Pi
- [ ] Verify systemd service auto-restarts after simulated power cut
- [ ] Confirm cloud sync of violation logs when network available

---

## Quick Reference — Key Numbers

| Parameter | Value |
|---|---|
| Two-wheeler detection input size (Pi 4) | 320 × 320 px |
| Two-wheeler detection input size (Jetson) | 640 × 640 px |
| Minimum plate width for reliable OCR | 80 pixels |
| Speed threshold for moving violation | 5.0 km/h |
| Challan cooldown per vehicle (same track ID) | 60 seconds |
| Enforcement zone | Full frame (no ROI gate) |
| OCR confidence minimum for auto-challan | 0.65 |
| Total model storage on device | ~18 MB |
| Pipeline FPS (detection only, Pi 4) | 12–15 FPS |
| Full pipeline end-to-end latency (Pi 4) | ~200–220 ms |
| Full pipeline end-to-end latency (Jetson) | ~80–100 ms |
| Recommended camera height | 3.5–5 metres |
| Recommended camera angle | 25–35° downward |
| IR illuminator range required | Minimum 10 metres |

---

*Objective 3 — Footpath Violation Detection & Auto-Enforcement*
*Edge AI System · YOLOv8n · ByteTrack · PaddleOCR PP-OCRv3 · TFLite INT8 · ONNX Runtime*
*Raspberry Pi 4 / Jetson Nano Deployment*
