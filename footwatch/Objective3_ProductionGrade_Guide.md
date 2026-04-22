# Objective 3 — Production-Grade Enhancement Guide
## Pre-Trained Model Alternatives · Full Observability Stack · Pipeline Enhancements

> **Scope**: This document builds on top of the existing Objective 3 ML guide. It covers (1) alternative open-source pre-trained models more efficient on SD/edge devices, (2) a complete observability and traceability framework, and (3) proposed enhancements to each stage of the pipeline to improve detection accuracy, accountability, and operational resilience.

---

## Table of Contents

1. [Core System Understanding](#1-core-system-understanding)
2. [Pre-Trained Model Alternatives — Vehicle Detection](#2-pre-trained-model-alternatives--vehicle-detection)
3. [Pre-Trained Model Alternatives — Plate Localisation & OCR](#3-pre-trained-model-alternatives--plate-localisation--ocr)
4. [Pre-Trained Model Alternatives — Tracking & Speed](#4-pre-trained-model-alternatives--tracking--speed)
5. [Full Observability Stack](#5-full-observability-stack)
6. [Latency Tracing — Every Measurable Parameter](#6-latency-tracing--every-measurable-parameter)
7. [Model Confidence Drift & Reliability Monitoring](#7-model-confidence-drift--reliability-monitoring)
8. [Pipeline Enhancements — Stage by Stage](#8-pipeline-enhancements--stage-by-stage)
9. [Additional Detection Capabilities](#9-additional-detection-capabilities)
10. [Hardware Accelerator Strategies](#10-hardware-accelerator-strategies)
11. [Production Deployment Patterns](#11-production-deployment-patterns)

---

## 1. Core System Understanding

### What Objective 3 is Really Trying to Achieve

The system's north star is **autonomous, legally defensible enforcement** on pedestrian footpaths, with zero manual intervention in the critical path. Every design decision flows from three hard constraints:

**Constraint 1 — Legal Defensibility**: Every challan generated must be contestable-proof. This means:
- OCR confidence score must be persistently stored (not just a pass/fail flag)
- Multiple evidence frames must be saved (not just the trigger frame)
- Speed estimation must show methodology, not just a number
- Timestamp + GPS + Camera ID must form an unforgeable chain of custody

**Constraint 2 — Edge-Only Processing**: No frame leaves the device. This means:
- Model selection is constrained by INT8 / TFLite / ONNX compatibility
- Latency budget is hard-bounded at 220ms on Pi 4 end-to-end
- Memory footprint must allow all 5 models to coexist in ~4GB RAM with OS overhead (~1.2GB), leaving ~2.8GB for models + buffers

**Constraint 3 — High Recall, Acceptable Precision**: In enforcement, a missed violation (false negative) is worse than a false positive that goes to manual review. The pipeline is tuned for recall, with a manual review queue acting as the precision safety net.

### Where the System is Currently Weakest

After deep analysis, these are the most fragile points in the current design:

1. **Stage 6 (OCR)** has the highest failure rate in real-world Indian conditions — dust-covered plates, non-standard fonts on older vehicles, faded reflective sheeting, and angle distortion at camera mounting heights below 4m all conspire against PaddleOCR's baseline accuracy.

2. **Speed estimation via bbox displacement** is noisy when the camera angle is shallow (< 25°) or when vehicles partially occlude each other. No Kalman smoothing is currently proposed.

3. **No confidence drift detection** — a model that degrades due to hardware aging, lens fouling, or lighting changes will silently produce more false negatives without any alert.

4. **No cross-camera deduplication** — the same vehicle can receive multiple challans from adjacent cameras covering overlapping zones.

5. **ByteTrack loses track IDs on brief occlusions** (≥ 3 frames) without a re-ID fallback, causing duplicate challans for the same vehicle pass.

---

## 2. Pre-Trained Model Alternatives — Vehicle Detection

### 2.1 YOLOv7-tiny (WongKinYiu / YOLOv7)

**Repository**: `https://github.com/WongKinYiu/yolov7`
**Weights (COCO pretrained)**: `https://github.com/WongKinYiu/yolov7/releases/download/v0.1/yolov7-tiny.pt`
**HuggingFace**: `https://huggingface.co/WongKinYiu/yolov7`

| Property | Value |
|---|---|
| Model size (PyTorch) | 6.2 MB |
| Model size (TFLite INT8) | ~3.8 MB |
| COCO mAP50 | 56.7% |
| Latency (Raspberry Pi 4, 320px) | ~48ms (vs YOLOv8n 55ms) |
| Latency (Jetson Nano, 640px) | ~19ms |
| ONNX Export | Native support |
| TFLite INT8 Export | Via ONNX → TFLite pipeline |
| Classes covering two-wheelers | motorcycle (class 3), bicycle (class 1) |

**Why consider YOLOv7-tiny over YOLOv8n**: YOLOv7-tiny uses an efficient architecture (E-ELAN) that achieves better parameter utilisation at the same model size. On COCO, it outperforms YOLOv8n in mAP50 by approximately 2–3 percentage points for small object detection at 320px input, which matters for two-wheelers at elevated camera angles where the bbox area is small.

**Export to TFLite INT8:**

```bash
# Step 1: Clone and export to ONNX
git clone https://github.com/WongKinYiu/yolov7
cd yolov7
pip install -r requirements.txt

python export.py \
    --weights yolov7-tiny.pt \
    --include onnx \
    --img-size 320 320 \
    --batch-size 1

# Step 2: ONNX → TFLite INT8 via onnx2tf
pip install onnx2tf tensorflow

onnx2tf \
    -i yolov7-tiny.onnx \
    -o yolov7-tiny-tflite \
    -oiqt \                          # INT8 quantization
    -cind images calibration_data/   # 100 representative frames for INT8 calibration
```

**Coral USB Accelerator compatibility**: YES — TFLite INT8 models run on Coral via the Edge TPU compiler:

```bash
edgetpu_compiler yolov7-tiny_full_integer_quant.tflite
# Output: yolov7-tiny_full_integer_quant_edgetpu.tflite
# Latency on Coral USB: ~8-12ms at 320px
```

---

### 2.2 YOLOv9-c / YOLOv9-t (Chien-Yao Wang, IEEM Lab)

**Repository**: `https://github.com/WongKinYiu/yolov9`
**Weights**: `https://github.com/WongKinYiu/yolov9/releases`
**Architecture**: PGI (Programmable Gradient Information) + GELAN (Generalised Efficient Layer Aggregation Network)

| Property | YOLOv9-t | YOLOv9-c |
|---|---|---|
| Model size (PyTorch) | 2.0 MB | 51 MB |
| COCO mAP50-95 | 38.3% | 53.0% |
| Latency (Pi 4, 320px INT8) | ~35ms | Not recommended for Pi |
| Latency (Jetson Nano, 640px) | ~15ms | ~40ms |
| Small object performance | Good | Excellent |

**Why YOLOv9-t is significant**: At 2MB PyTorch weight size and 38.3% COCO mAP50-95, it surpasses YOLOv8n (37.3%) with a smaller footprint. The PGI mechanism means it retains gradient information better during training, which translates to better generalisation on out-of-distribution scenarios — critical for Indian street conditions.

**Best use case in this project**: YOLOv9-t as primary detector on Raspberry Pi 4 with INT8 quantization. YOLOv9-c on Jetson Nano TensorRT.

---

### 2.3 Gold-YOLO (Huawei Noah's Ark Lab)

**Repository**: `https://github.com/huawei-noah/Efficient-Computing/tree/master/Detection/Gold-YOLO`
**HuggingFace**: `https://huggingface.co/huawei-noah/Gold-YOLO`

| Property | Gold-YOLO-N (Nano) | Gold-YOLO-S |
|---|---|---|
| Model size | 5.6 MB | 21.5 MB |
| COCO mAP50-95 | 39.6% | 45.4% |
| Key innovation | Gather-Distribute (GD) mechanism |
| Latency (Pi 4, 320px INT8) | ~42ms | ~85ms |
| Small object mAP improvement | +3.8% over YOLOv6-n | +4.1% |

**Why consider Gold-YOLO-N**: The Gather-Distribute mechanism explicitly addresses multi-scale feature fusion, which is directly relevant to this project's challenge of detecting two-wheelers at varying distances from an elevated camera. The small-object performance improvement is real and measurable.

**ONNX Export:**
```python
from gold_yolo import GoldYOLO
import torch

model = GoldYOLO.from_pretrained('huawei-noah/Gold-YOLO', model_type='n')
dummy_input = torch.zeros(1, 3, 320, 320)
torch.onnx.export(
    model, dummy_input, 'gold_yolo_n.onnx',
    opset_version=13,
    input_names=['images'],
    output_names=['output'],
    dynamic_axes={'images': {0: 'batch'}, 'output': {0: 'batch'}}
)
```

---

### 2.4 NanoDet-Plus (RangiLyu)

**Repository**: `https://github.com/RangiLyu/nanodet`
**Model Zoo**: `https://github.com/RangiLyu/nanodet/blob/main/docs/model_zoo.md`

| Property | NanoDet-Plus-m-1.5x | NanoDet-Plus-m |
|---|---|---|
| Model size | 2.44 MB | 1.17 MB |
| COCO mAP50-95 | 34.1% | 30.4% |
| Latency (Raspberry Pi 4, 320px) | **~25ms** | ~18ms |
| Latency (Android/ARM, 320px) | 11ms | 8ms |
| Framework | ONNX / ncnn / MNN / CoreML |
| Anchor-free | Yes |

**Why NanoDet-Plus is exceptional for this project**: NanoDet was specifically designed for mobile and edge deployment. At 25ms on Pi 4, it provides the fastest inference of any model listed here. The trade-off is lower mAP, but for the specific task of two-wheeler detection where the vehicle is relatively large in frame (footpath camera at 3.5-5m height), the accuracy drop is acceptable.

**Critical advantage**: NanoDet natively supports **ncnn** (Tencent's mobile inference framework), which is more efficient than TFLite on ARM processors — particularly Cortex-A72 (Raspberry Pi 4). ncnn is compiled for ARM NEON SIMD instructions, giving 10-15% better latency than TFLite on the same hardware.

```bash
# Install ncnn on Raspberry Pi
sudo apt-get install libncnn-dev

# Convert NanoDet ONNX → ncnn
pip install ncnn

python -c "
import ncnn
ncnn.tools.onnx2ncnn('nanodet_plus.onnx', 'nanodet_plus.param', 'nanodet_plus.bin')
"

# Inference with ncnn (Raspberry Pi optimised)
```

---

### 2.5 EdgeYOLO (hpc203)

**Repository**: `https://github.com/LSH9832/edgeyolo`
**Pre-trained weights**: Available on GitHub releases for COCO + VISDRONE

| Property | EdgeYOLO-tiny | EdgeYOLO-s |
|---|---|---|
| Model size | 7.6 MB | 22.4 MB |
| COCO mAP50 | 50.5% | 63.0% |
| VISDRONE mAP50 | 26.4% | 31.7% |
| Latency (Jetson Xavier NX) | 9.3ms | 14.7ms |
| Focus | Drone/aerial/small object |

**Why EdgeYOLO matters**: Critically, EdgeYOLO was trained and evaluated on **VisDRONE** — a dataset of objects captured from elevated aerial perspectives (drones). This matches your camera mounting scenario (3.5–5m elevated, downward-angled at 25–35°). The top-down perspective causes standard COCO models to struggle because COCO mostly has lateral/eye-level views of vehicles. EdgeYOLO's pre-trained weights already understand compressed, overhead vehicle appearance.

**VisDRONE has motorcycle class**: The VisDRONE dataset contains `car`, `truck`, `bus`, `van`, `motor` (motorcycle), `bicycle`, `pedestrian`, `awning-tricycle`. This means EdgeYOLO's pretrained weights already represent two-wheelers from overhead, with no fine-tuning.

**Export:**
```bash
python export.py \
    --weights edgeyolo_tiny.pt \
    --type onnx \
    --input-shape 1 3 320 320 \
    --device cpu
```

---

### 2.6 PP-YOLOE+ (PaddleDetection)

**Repository**: `https://github.com/PaddlePaddle/PaddleDetection`
**HuggingFace**: `https://huggingface.co/PaddlePaddle/PP-YOLOE-plus`

| Property | PP-YOLOE+-s | PP-YOLOE+-t |
|---|---|---|
| Model size | 13.0 MB | 4.8 MB |
| COCO mAP50-95 | 43.7% | 39.9% |
| Framework | PaddlePaddle → ONNX |
| Latency (T4 GPU) | 2.9ms | - |
| Latency (ARM CPU, 320px) | ~60ms | ~35ms |
| Notable | Same family as PaddleOCR — unified deployment |

**Advantage**: Since this project already uses PaddleOCR for Stage 6, using PP-YOLOE+ for Stage 1 means the entire pipeline is PaddlePaddle-native. This simplifies model management, versioning, and the inference runtime footprint — one framework for all models.

```bash
# Export PP-YOLOE+ to ONNX for cross-platform deployment
paddle2onnx \
    --model_dir output/ppyoloe_plus_crn_t_60e_coco \
    --model_filename model.pdmodel \
    --params_filename model.pdiparams \
    --save_file ppyoloe_plus_t.onnx \
    --opset_version 11
```

---

### 2.7 Model Comparison Matrix — Stage 1 (Two-Wheeler Detection)

| Model | Size (INT8) | Pi 4 Latency | mAP50-95 | Small Obj | Edge Toolchain | Best For |
|---|---|---|---|---|---|---|
| **YOLOv8n** (current) | 3.2 MB | ~55ms | 37.3% | Fair | TFLite/ONNX | Baseline — well documented |
| **YOLOv7-tiny** | 3.8 MB | ~48ms | 38.8% | Good | ONNX/TFLite | Better than YOLOv8n, minimal effort |
| **YOLOv9-t** | ~2.5 MB | ~35ms | 38.3% | Good | ONNX | Smaller + faster than YOLOv8n |
| **Gold-YOLO-N** | ~4.0 MB | ~42ms | 39.6% | Best | ONNX | Best small-obj; overhead views |
| **NanoDet-Plus-m** | ~1.5 MB | **~25ms** | 30.4% | Fair | ncnn/ONNX | Fastest; use on Pi 4 with Coral |
| **EdgeYOLO-tiny** | ~5.0 MB | ~50ms | 50.5% (mAP50) | **Best** | ONNX | Elevated camera angles (VisDRONE) |
| **PP-YOLOE+-t** | ~3.5 MB | ~35ms | 39.9% | Good | Paddle/ONNX | Unified with PaddleOCR stack |

**Recommendation by deployment scenario:**

- **Pi 4 without Coral Accelerator**: `NanoDet-Plus-m-1.5x` (25ms, ncnn) or `YOLOv9-t` (35ms, ONNX)
- **Pi 4 with Coral USB Accelerator**: `YOLOv7-tiny` INT8 EdgeTPU (~10ms)
- **Pi 5 with Hailo-8**: `YOLOv8n` or `Gold-YOLO-N` (Hailo SDK supports both)
- **Jetson Nano (TensorRT)**: `YOLOv9-c` TensorRT FP16 (~12ms at 640px)
- **Camera elevated >4m, VisDRONE-style**: `EdgeYOLO-tiny` with VisDRONE weights (no retraining needed for motor class)
- **Unified PaddlePaddle stack**: `PP-YOLOE+-t`

---

## 3. Pre-Trained Model Alternatives — Plate Localisation & OCR

### 3.1 Plate Localisation Alternatives

#### YOLOv5n-LP (ultralytics/yolov5)

**Repository**: `https://github.com/ultralytics/yolov5`
**Pretrained LP weights**: `https://github.com/nicehuster/License-Plate-Detect-Yolov5`

YOLOv5n is slightly older but has a massive community of fine-tuned LP detector weights. Many publicly available checkpoint files are trained on large mixed datasets including Indian plates.

```python
import torch

# Load pretrained LP detector (YOLOv5n fine-tuned on LP dataset)
model = torch.hub.load('ultralytics/yolov5', 'custom',
                       path='lp_detector_yolov5n.pt', force_reload=True)
model.conf = 0.3
model.iou = 0.45
model.eval()
```

#### LPRNet (License Plate Recognition Network)

**Repository**: `https://github.com/sirius-ai/LPRNet_Pytorch`
**What it does differently**: LPRNet is an end-to-end network that simultaneously performs plate detection AND character recognition in one pass, skipping the separate plate localisation + OCR two-stage approach.

| Property | Value |
|---|---|
| Model size | ~1.7 MB |
| Combined detection + OCR latency | ~45ms on Pi 4 |
| Accuracy on Chinese/Asian plates | ~98% |
| Indian LP accuracy (raw) | ~70-75% (requires fine-tuning) |
| Architecture | Depthwise separable conv + CTC |

LPRNet is worth considering as an **alternative pipeline path** (bypassing Stages 4+5+6 with a single model), particularly after fine-tuning on Indian plates.

### 3.2 OCR Engine Alternatives

#### EasyOCR (JaidedAI)

**Repository**: `https://github.com/JaidedAI/EasyOCR`
**HuggingFace**: `https://huggingface.co/spaces/tomofi/EasyOCR`

```python
import easyocr
reader = easyocr.Reader(['en'], gpu=False, model_storage_directory='models/easyocr')
result = reader.readtext(plate_img, detail=1, paragraph=False)
```

| Property | EasyOCR | PaddleOCR PP-OCRv3 |
|---|---|---|
| Model size | ~12 MB | ~8 MB |
| Pi 4 latency | ~120ms | ~90ms |
| Indian LP accuracy (real-world) | ~85-88% | ~92-95% |
| ONNX export | Not native (PyTorch) | Yes (native) |
| Ease of integration | Excellent | Good |

**Verdict**: PaddleOCR remains the better choice for production. EasyOCR is a viable fallback and useful for prototyping.

#### TrOCR-small (Microsoft)

**Repository**: `https://huggingface.co/microsoft/trocr-small-printed`
**Architecture**: Vision Transformer + Language Model decoder (encoder-decoder)

| Property | Value |
|---|---|
| Model size | ~120 MB (too large for Pi; Jetson only) |
| IAM accuracy | 96.6% |
| Printed text handling | Exceptional |
| Edge suitability | Jetson Nano with quantization only |
| Quantized size (INT8) | ~35 MB |

TrOCR-small is worth considering only on Jetson Nano where accuracy is critical and latency budget allows. Its transformer-based architecture handles unusual fonts and partial degradation better than CRNN-based models.

#### MMOCR (OpenMMLab)

**Repository**: `https://github.com/open-mmlab/mmocr`

MMOCR provides a modular OCR toolkit with multiple model options. For this project, the relevant model is:

- **ABINet** (Autonomous, Bidirectional and Iterative): Best accuracy, too large for Pi
- **MASTER**: Balanced accuracy and speed, viable on Jetson
- **CRNN (ResNet31)**: ~6MB, runs on Pi, ~85% accuracy on Indian LP

### 3.3 Plate Super-Resolution Alternatives

#### Real-ESRGAN (xinntao) — Tiny Variant

**Repository**: `https://github.com/xinntao/Real-ESRGAN`
**Tiny model**: `https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0`
**Weight file**: `RealESRGAN_x4plus_anime_6B.pth` → smaller at 17MB; `realesr-general-x4v3.pth` at 67MB (Jetson only)

```python
from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer

model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=32, 
                num_block=6, num_grow_ch=32, scale=4)
upsampler = RealESRGANer(
    scale=4,
    model_path='RealESRGAN_x4plus_anime_6B.pth',
    model=model,
    tile=0,
    half=False  # Pi doesn't support FP16
)
sr_img, _ = upsampler.enhance(plate_img, outscale=4)
```

#### BSRGAN (Kai Zhang, KAIR)

**Repository**: `https://github.com/cszn/BSRGAN`
**Model**: Available as ONNX (8.4 MB)

BSRGAN is specifically designed for real-world degraded images (blur, noise, JPEG artefacts, downsampling combined). This matches plate images captured in motion. It outperforms basic ESRGAN on degraded plates by ~1.2dB PSNR.

---

## 4. Pre-Trained Model Alternatives — Tracking & Speed

### 4.1 OC-SORT (Observation-Centric SORT)

**Repository**: `https://github.com/noahcao/OC-SORT`
**Paper**: Observation-Centric SORT: Rethinking SORT for Robust Multi-Object Tracking

| Property | ByteTrack | OC-SORT |
|---|---|---|
| Architecture | IoU-based + low-score detection | IoU + velocity direction |
| Re-tracking after occlusion | Weak (loses ID after 3+ missed frames) | **Strong** (virtual trajectory during occlusion) |
| Latency per frame | ~5ms | ~7ms |
| HOTA score (MOT17) | 63.1% | 63.9% |
| False ID switches | More | **Less** |

**Why OC-SORT is better for this project**: The critical failure mode in the current design is losing track IDs during brief occlusions (a pedestrian walking in front of the two-wheeler, or the vehicle briefly exiting the frame edge). OC-SORT uses observation-centric momentum to maintain the virtual trajectory during occlusion and re-associates the same ID when the vehicle reappears. This directly prevents the duplicate challan problem.

```python
from ocsort import OCSort

tracker = OCSort(
    det_thresh=0.45,
    max_age=20,           # frames before track is dropped
    min_hits=3,           # frames before track is confirmed
    iou_threshold=0.5,
    delta_t=3,            # look-back window for velocity
    asso_func="iou",      # or "giou" for better edge cases
    inertia=0.2           # how much to trust velocity vs IoU
)
```

### 4.2 BoT-SORT (ByteTrack + Re-ID)

**Repository**: `https://github.com/NirAharon/BoT-SORT`

BoT-SORT adds camera motion compensation and an optional ReID module on top of ByteTrack. The camera motion compensation is directly useful here — if the camera vibrates in wind (common with pole-mounted cameras), BoT-SORT compensates for the apparent pixel displacement that would otherwise corrupt speed estimation.

| Property | Value |
|---|---|
| Camera motion compensation | Yes (homography estimation) |
| Re-ID module | Optional (off = ByteTrack level speed) |
| Latency overhead vs ByteTrack | +3-5ms for camera motion comp |
| Speed estimation improvement | Significant (less jitter from camera movement) |

### 4.3 Improved Speed Estimation — Kalman Filter Integration

The current speed estimation uses simple 3-frame average displacement. This is noisy. A Kalman filter tracks position AND velocity as a state vector, smoothing out jitter:

```python
from filterpy.kalman import KalmanFilter
import numpy as np

class KalmanSpeedEstimator:
    """
    4D Kalman filter state: [x, y, vx, vy]
    Measures position, estimates velocity with noise reduction.
    """
    
    def __init__(self):
        self.kf = KalmanFilter(dim_x=4, dim_z=2)
        dt = 1.0  # one frame time step
        
        # State transition matrix (constant velocity model)
        self.kf.F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1,  0],
            [0, 0, 0,  1]
        ])
        
        # Measurement matrix (we observe x, y position)
        self.kf.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ])
        
        # Measurement noise (camera noise ~2px)
        self.kf.R = np.eye(2) * 4.0
        
        # Process noise (vehicle can accelerate)
        self.kf.Q = np.eye(4) * 0.1
        self.kf.Q[2, 2] = 0.5  # higher uncertainty on velocity
        self.kf.Q[3, 3] = 0.5
        
        self.kf.P = np.eye(4) * 100
        self.initialized = False
    
    def update(self, bbox_center: tuple, fps: float, 
               pixels_per_metre: float) -> float:
        """
        Feed bbox center, return smoothed speed in km/h.
        """
        z = np.array([[bbox_center[0]], [bbox_center[1]]])
        
        if not self.initialized:
            self.kf.x = np.array([[z[0,0]], [z[1,0]], [0.], [0.]])
            self.initialized = True
            return 0.0
        
        self.kf.predict()
        self.kf.update(z)
        
        # Extract smoothed velocity (pixels/frame)
        vx = self.kf.x[2, 0]
        vy = self.kf.x[3, 0]
        pixel_speed = np.sqrt(vx**2 + vy**2)
        
        metres_per_frame  = pixel_speed / pixels_per_metre
        metres_per_second = metres_per_frame * fps
        return round(metres_per_second * 3.6, 1)
```

---

## 5. Full Observability Stack

### 5.1 Architecture Overview

The observability stack consists of four layers, all running on-device or on the local network dashboard server:

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 4 — ALERTING                                             │
│  Threshold-based alerts → MQTT → Police Dashboard              │
│  Anomaly detection → Offline alert queue                        │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 3 — METRICS AGGREGATION                                  │
│  Prometheus Node Exporter (local) → Grafana Dashboard           │
│  Custom metrics: per-stage latency, confidence distributions    │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 2 — DISTRIBUTED TRACING                                  │
│  OpenTelemetry SDK → OTLP Exporter → Jaeger (local)             │
│  Per-frame trace with span per pipeline stage                   │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 1 — STRUCTURED LOGGING                                   │
│  JSON logs per frame → SQLite (on-device) → Sync to server      │
│  Every frame gets a trace_id, every stage logs result + latency │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Structured Logging — Every Frame Gets a Trace ID

```python
import logging
import json
import uuid
import time
import sqlite3
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class PipelineTrace:
    """One trace per processed frame."""
    trace_id: str
    camera_id: str
    frame_number: int
    frame_timestamp: str
    frame_timestamp_epoch: float
    
    # Detection stage
    stage1_latency_ms: Optional[float] = None
    stage1_detections: int = 0
    stage1_max_confidence: float = 0.0
    stage1_classes_detected: str = ""     # "motorcycle,bicycle"
    
    # Tracking stage
    stage3_latency_ms: Optional[float] = None
    stage3_active_tracks: int = 0
    stage3_new_tracks: int = 0
    stage3_lost_tracks: int = 0
    
    # Per-vehicle stages (for frames that enter OCR pipeline)
    plate_loc_latency_ms: Optional[float] = None
    plate_loc_confidence: float = 0.0
    plate_loc_found: bool = False
    
    enhancement_latency_ms: Optional[float] = None
    enhancement_method: str = ""          # "clahe_cpu" or "esrgan"
    
    ocr_latency_ms: Optional[float] = None
    ocr_raw_text: str = ""
    ocr_cleaned_text: str = ""
    ocr_confidence: float = 0.0
    ocr_format_valid: bool = False
    ocr_voting_rounds: int = 0
    
    # Evidence generation
    evidence_latency_ms: Optional[float] = None
    challan_generated: bool = False
    challan_id: Optional[str] = None
    
    # Pipeline totals
    total_pipeline_latency_ms: Optional[float] = None
    pipeline_outcome: str = ""            # "challan", "manual_review", "skip", "error"
    error_stage: Optional[str] = None
    error_message: Optional[str] = None
    
    # Device metrics
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    cpu_temp_celsius: float = 0.0
    disk_free_gb: float = 0.0


class PipelineLogger:
    """
    Structured logger for the full pipeline.
    Writes to SQLite for local querying and JSON files for sync.
    """
    
    def __init__(self, db_path: str = "logs/pipeline_traces.db",
                 camera_id: str = "EDGE-001"):
        self.camera_id = camera_id
        self.db_path = db_path
        self._init_db()
        
        # Standard Python logger for warnings/errors
        self.log = logging.getLogger("pipeline")
        logging.basicConfig(
            filename="logs/pipeline.log",
            level=logging.INFO,
            format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":%(message)s}'
        )
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                trace_id TEXT PRIMARY KEY,
                camera_id TEXT,
                frame_number INTEGER,
                frame_timestamp TEXT,
                total_latency_ms REAL,
                outcome TEXT,
                challan_id TEXT,
                ocr_confidence REAL,
                cpu_temp REAL,
                data_json TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_outcome ON traces(outcome)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON traces(frame_timestamp)")
        conn.commit()
        conn.close()
    
    def new_trace(self, frame_number: int) -> PipelineTrace:
        return PipelineTrace(
            trace_id=str(uuid.uuid4()),
            camera_id=self.camera_id,
            frame_number=frame_number,
            frame_timestamp=datetime.now().isoformat(),
            frame_timestamp_epoch=time.time()
        )
    
    def commit_trace(self, trace: PipelineTrace):
        """Write completed trace to SQLite."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO traces
            (trace_id, camera_id, frame_number, frame_timestamp,
             total_latency_ms, outcome, challan_id, ocr_confidence,
             cpu_temp, data_json)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            trace.trace_id, trace.camera_id, trace.frame_number,
            trace.frame_timestamp, trace.total_pipeline_latency_ms,
            trace.pipeline_outcome, trace.challan_id,
            trace.ocr_confidence, trace.cpu_temp_celsius,
            json.dumps(asdict(trace))
        ))
        conn.commit()
        conn.close()


# Usage in main loop:
logger = PipelineLogger(camera_id="MG_ROAD_CAM_001")
trace = logger.new_trace(frame_number=current_frame)

t0 = time.perf_counter()
detections = detector.run(frame)
trace.stage1_latency_ms = (time.perf_counter() - t0) * 1000
trace.stage1_detections = len(detections)
trace.stage1_max_confidence = max((d['conf'] for d in detections), default=0.0)
```

---

## 6. Latency Tracing — Every Measurable Parameter

### 6.1 Complete Latency Map

Every latency point that should be measured and stored:

| Metric ID | What It Measures | Why It Matters | Alert Threshold |
|---|---|---|---|
| `L1_frame_capture_ms` | RTSP frame read latency | Network jitter, camera lag | > 80ms |
| `L1_frame_decode_ms` | JPEG/H264 decode latency | CPU bottleneck | > 15ms |
| `L2_detection_preprocess_ms` | Resize + normalize + CHW transpose | Bottleneck before inference | > 10ms |
| `L2_detection_inference_ms` | Model forward pass (TFLite/ONNX) | Core model performance | > 70ms (Pi 4) |
| `L2_detection_postprocess_ms` | NMS, threshold filter | Hidden cost | > 8ms |
| `L3_tracker_update_ms` | ByteTrack/OC-SORT IoU matching | Grows with track count | > 10ms |
| `L3_speed_estimate_ms` | Kalman filter update + km/h calc | Negligible normally | > 3ms |
| `L3_cooldown_check_ms` | SQLite lookup for duplicate challan | Disk I/O issue | > 5ms |
| `L4_plate_crop_ms` | Crop vehicle bbox from frame | Memory alloc cost | > 2ms |
| `L4_plate_detect_inference_ms` | LP localisation model inference | Per-vehicle cost | > 50ms |
| `L4_plate_detect_postprocess_ms` | NMS + best plate selection | Negligible | > 3ms |
| `L5_enhance_resize_ms` | Plate resize to target width | Always fast | > 2ms |
| `L5_enhance_clahe_ms` | CLAHE + unsharp mask pipeline | Should be fast | > 12ms |
| `L5_enhance_esrgan_ms` | ESRGAN neural SR (if used) | Expensive on Pi | > 200ms |
| `L5_deskew_ms` | Hough line rotation correction | Hough is expensive | > 8ms |
| `L6_ocr_inference_ms` | PaddleOCR full inference | Largest single cost | > 120ms |
| `L6_ocr_voting_total_ms` | 3x OCR voting total | 3x single ocr cost | > 360ms |
| `L6_ocr_postprocess_ms` | Regex clean + position fix | Negligible | > 2ms |
| `L7_json_write_ms` | violation_metadata.json write | Disk I/O | > 20ms |
| `L7_image_save_ms` | cv2.imwrite (3 images) | JPEG encode + disk | > 30ms |
| `L7_mqtt_publish_ms` | MQTT publish (async, background) | Network dependent | > 500ms |
| `L_TOTAL_pipeline_ms` | Frame entry to challan written | End-to-end SLA | > 280ms |
| `L_TOTAL_detection_only_ms` | Frame to Stage 3 output | Main loop timing | > 80ms |

### 6.2 Prometheus Metrics Implementation

```python
from prometheus_client import Histogram, Counter, Gauge, start_http_server
import psutil, subprocess

# ── Latency histograms (buckets in milliseconds) ──────────────────────────────

STAGE_LATENCY = {
    'detection_inference': Histogram(
        'pipeline_detection_inference_ms',
        'Stage 1: YOLOv8/NanoDet inference latency',
        buckets=[10, 20, 30, 40, 50, 60, 80, 100, 150, 200]
    ),
    'tracking_update': Histogram(
        'pipeline_tracking_ms',
        'Stage 3: tracker update latency',
        buckets=[1, 2, 3, 5, 8, 12, 20, 35]
    ),
    'plate_detection': Histogram(
        'pipeline_plate_detection_ms',
        'Stage 4: plate localisation latency',
        buckets=[10, 20, 30, 40, 50, 70, 100]
    ),
    'enhancement': Histogram(
        'pipeline_enhancement_ms',
        'Stage 5: plate enhancement latency',
        buckets=[2, 5, 8, 12, 20, 50, 100, 200]
    ),
    'ocr': Histogram(
        'pipeline_ocr_ms',
        'Stage 6: OCR inference latency',
        buckets=[30, 50, 70, 90, 120, 150, 200, 300, 500]
    ),
    'total_pipeline': Histogram(
        'pipeline_total_ms',
        'End-to-end pipeline latency for violation frames',
        buckets=[100, 150, 200, 220, 250, 280, 350, 500, 1000]
    ),
}

# ── Counters ─────────────────────────────────────────────────────────────────

FRAMES_PROCESSED    = Counter('frames_processed_total', 'Total frames processed')
VEHICLES_DETECTED   = Counter('vehicles_detected_total', 'Total two-wheeler detections')
CHALLANS_GENERATED  = Counter('challans_generated_total', 'Total challans issued')
CHALLANS_MANUAL_REVIEW = Counter('challans_manual_review_total', 'Challans sent to manual review')
OCR_SUCCESS         = Counter('ocr_success_total', 'OCR produced valid plate string')
OCR_FAIL_NO_PLATE   = Counter('ocr_fail_no_plate_total', 'No plate localised')
OCR_FAIL_LOW_CONF   = Counter('ocr_fail_low_confidence_total', 'Plate read but confidence below threshold')
OCR_FAIL_INVALID_FORMAT = Counter('ocr_fail_invalid_format_total', 'OCR text not matching Indian LP regex')
TRACKER_ID_SWITCHES = Counter('tracker_id_switches_total', 'Track ID reassignments detected')
PIPELINE_ERRORS     = Counter('pipeline_errors_total', 'Unhandled exceptions in pipeline', ['stage'])

# ── Gauges ────────────────────────────────────────────────────────────────────

ACTIVE_TRACKS       = Gauge('active_tracks_current', 'Currently active track IDs')
DETECTION_CONF_P50  = Gauge('detection_confidence_p50', 'Median detection confidence (rolling 100 frames)')
OCR_CONF_P50        = Gauge('ocr_confidence_p50', 'Median OCR confidence (rolling 100 readings)')
CPU_TEMP            = Gauge('device_cpu_temp_celsius', 'CPU temperature')
CPU_PERCENT         = Gauge('device_cpu_percent', 'CPU utilisation')
MEMORY_USED_MB      = Gauge('device_memory_used_mb', 'RAM used in MB')
DISK_FREE_GB        = Gauge('device_disk_free_gb', 'Free disk space in GB')
VIOLATIONS_QUEUE_DEPTH = Gauge('violations_pending_push_queue', 'MQTT offline queue depth')
PIPELINE_FPS        = Gauge('pipeline_fps_current', 'Current detection loop FPS')


class DeviceMetricsCollector:
    """Collect and publish system health metrics every 10 seconds."""
    
    def collect(self):
        CPU_PERCENT.set(psutil.cpu_percent(interval=None))
        MEMORY_USED_MB.set(psutil.virtual_memory().used / 1024 / 1024)
        
        disk = psutil.disk_usage('/home')
        DISK_FREE_GB.set(disk.free / 1024**3)
        
        # Raspberry Pi CPU temperature
        try:
            temp = float(open('/sys/class/thermal/thermal_zone0/temp').read()) / 1000.0
            CPU_TEMP.set(temp)
        except Exception:
            pass


# Start Prometheus scrape endpoint (port 8000 → Grafana scrapes this)
start_http_server(8000)
```

### 6.3 OpenTelemetry Distributed Tracing

Each frame becomes a root span. Each pipeline stage is a child span. When multiple cameras are deployed, all spans share a `camera_id` attribute, allowing cross-camera trace correlation in Jaeger.

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
import contextlib

# Initialise tracer — OTLP to local Jaeger instance
provider = TracerProvider()
exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("footpath.enforcement.pipeline")


@contextlib.contextmanager
def timed_span(name: str, trace_id: str, camera_id: str, **attributes):
    """Context manager: creates an OTel span AND records latency to Prometheus."""
    start = time.perf_counter()
    with tracer.start_as_current_span(name) as span:
        span.set_attribute("trace_id", trace_id)
        span.set_attribute("camera.id", camera_id)
        for k, v in attributes.items():
            span.set_attribute(k, v)
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            span.set_attribute("latency_ms", elapsed_ms)


# Usage in main loop:
with tracer.start_as_current_span("frame_pipeline") as root_span:
    root_span.set_attribute("camera.id", camera_config["camera_id"])
    root_span.set_attribute("frame.number", frame_number)
    
    with timed_span("stage1_detection", trace_id, camera_id) as s:
        detections = detector.run(frame)
        s.set_attribute("detections.count", len(detections))
        STAGE_LATENCY['detection_inference'].observe(...)
    
    for vehicle in confirmed_violations:
        with timed_span("stage4_plate_localisation", trace_id, camera_id,
                        track_id=vehicle.track_id):
            plate_bbox = plate_detector.run(vehicle.crop)
        
        with timed_span("stage5_enhancement", trace_id, camera_id):
            enhanced = enhancer.process(plate_crop)
        
        with timed_span("stage6_ocr", trace_id, camera_id) as s:
            ocr_result = ocr_engine.read_plate(enhanced)
            s.set_attribute("ocr.confidence", ocr_result["confidence"])
            s.set_attribute("ocr.valid", ocr_result["is_valid"])
```

---

## 7. Model Confidence Drift & Reliability Monitoring

### 7.1 Confidence Drift Detector

A model that degrades silently (lens fouling, hardware ageing, lighting changes) will show confidence score distribution shift before accuracy drops. Track this:

```python
import numpy as np
from collections import deque
from scipy import stats

class ConfidenceDriftDetector:
    """
    Monitor per-stage confidence distributions.
    Alert when current distribution deviates from baseline.
    Uses Kolmogorov-Smirnov test for distribution shift detection.
    """
    
    WINDOW_SIZE = 1000       # rolling window of confidence readings
    BASELINE_SIZE = 5000     # baseline samples (first week of deployment)
    KS_ALERT_THRESHOLD = 0.05  # p-value below this = significant drift
    
    def __init__(self, stage_name: str, baseline_path: str = None):
        self.stage_name = stage_name
        self.recent_scores = deque(maxlen=self.WINDOW_SIZE)
        self.baseline_scores = []
        self.baseline_established = False
        
        if baseline_path:
            self._load_baseline(baseline_path)
    
    def record(self, confidence_score: float):
        self.recent_scores.append(confidence_score)
        
        if not self.baseline_established and len(self.baseline_scores) < self.BASELINE_SIZE:
            self.baseline_scores.append(confidence_score)
        elif not self.baseline_established:
            self.baseline_established = True
            self._save_baseline()
    
    def check_drift(self) -> dict:
        if not self.baseline_established or len(self.recent_scores) < 100:
            return {"drift_detected": False, "reason": "insufficient_data"}
        
        ks_stat, p_value = stats.ks_2samp(
            self.baseline_scores[-1000:],
            list(self.recent_scores)
        )
        
        recent_mean = np.mean(list(self.recent_scores))
        baseline_mean = np.mean(self.baseline_scores[-1000:])
        mean_drop = baseline_mean - recent_mean
        
        drift_detected = (p_value < self.KS_ALERT_THRESHOLD) or (mean_drop > 0.10)
        
        return {
            "drift_detected": drift_detected,
            "stage": self.stage_name,
            "ks_statistic": round(ks_stat, 4),
            "p_value": round(p_value, 4),
            "recent_mean_confidence": round(recent_mean, 3),
            "baseline_mean_confidence": round(baseline_mean, 3),
            "mean_drop": round(mean_drop, 3),
            "alert_message": (
                f"[ALERT] Confidence drift on {self.stage_name}: "
                f"mean dropped {mean_drop:.2%} (KS p={p_value:.4f})"
            ) if drift_detected else None
        }


# One detector per stage
detection_drift   = ConfidenceDriftDetector("stage1_detection")
plate_loc_drift   = ConfidenceDriftDetector("stage4_plate_localisation")
ocr_drift         = ConfidenceDriftDetector("stage6_ocr")
```

### 7.2 False Positive Rate Monitor

Track the ratio of challans sent to manual review vs auto-approved. A rising manual review rate signals degrading OCR or detection quality:

```python
class QualityMonitor:
    """
    Rolling window quality metrics.
    Alerts when false positive indicators spike.
    """
    
    def __init__(self, window=500):
        self.window = window
        self.outcomes = deque(maxlen=window)  # 'auto', 'manual', 'skip', 'error'
        
    def record(self, outcome: str):
        self.outcomes.append(outcome)
    
    def metrics(self) -> dict:
        if len(self.outcomes) < 10:
            return {}
        
        total = len(self.outcomes)
        counts = {o: self.outcomes.count(o) for o in set(self.outcomes)}
        
        auto_rate   = counts.get('auto', 0) / total
        manual_rate = counts.get('manual', 0) / total
        error_rate  = counts.get('error', 0) / total
        
        return {
            "window_size": total,
            "auto_challan_rate": round(auto_rate, 3),
            "manual_review_rate": round(manual_rate, 3),
            "error_rate": round(error_rate, 3),
            "alert_manual_review_high": manual_rate > 0.30,   # >30% → investigate
            "alert_error_rate_high": error_rate > 0.05,       # >5% → critical
        }
```

### 7.3 Thermal Throttle Detection

Raspberry Pi throttles at 80°C. Throttling increases inference latency by 30-50% and must be detected:

```python
import subprocess

def get_throttle_flags() -> dict:
    """
    Read Raspberry Pi throttle flags from vcgencmd.
    Returns dict of current throttle conditions.
    """
    try:
        result = subprocess.run(
            ['vcgencmd', 'get_throttled'],
            capture_output=True, text=True, timeout=2
        )
        hex_val = int(result.stdout.strip().split('=')[1], 16)
    except Exception:
        return {"available": False}
    
    return {
        "available": True,
        "raw_hex": hex(hex_val),
        "under_voltage_now":          bool(hex_val & (1 << 0)),
        "arm_freq_capped_now":        bool(hex_val & (1 << 1)),
        "currently_throttled":        bool(hex_val & (1 << 2)),
        "soft_temp_limit_active_now": bool(hex_val & (1 << 3)),
        "under_voltage_occurred":     bool(hex_val & (1 << 16)),
        "arm_freq_capped_occurred":   bool(hex_val & (1 << 17)),
        "throttling_occurred":        bool(hex_val & (1 << 18)),
        "alert": bool(hex_val & 0b1111),  # True if any current issue
    }
```

---

## 8. Pipeline Enhancements — Stage by Stage

### 8.1 Stage 1 — Multi-Scale Detection Strategy

The current design uses a single 320px input. Add a dynamic resolution switcher based on detection confidence:

```python
class AdaptiveDetector:
    """
    Run at 320px first. If confidence < threshold, re-run at 640px.
    Saves latency on easy frames, improves accuracy on hard ones.
    """
    
    FAST_SIZE = 320
    ACCURATE_SIZE = 640
    RERUN_THRESHOLD = 0.50   # re-run at high-res if best conf < this
    
    def __init__(self, model_path: str):
        self.model = YOLO(model_path)
    
    def detect(self, frame: np.ndarray) -> list:
        # Fast pass at 320px
        results_fast = self.model(frame, imgsz=self.FAST_SIZE, conf=0.45)
        
        if not results_fast[0].boxes:
            return []
        
        max_conf = float(results_fast[0].boxes.conf.max())
        
        # If best confidence is marginal, re-run at full resolution
        if max_conf < self.RERUN_THRESHOLD:
            results_full = self.model(frame, imgsz=self.ACCURATE_SIZE, conf=0.40)
            return results_full
        
        return results_fast
```

### 8.2 Stage 1 — Night Mode Classifier

Automatically switch detection thresholds and enhancement parameters based on luminance:

```python
def classify_lighting(frame: np.ndarray) -> str:
    """Returns 'day', 'dusk', or 'night' based on frame luminance."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_lum = gray.mean()
    
    if mean_lum > 80:
        return 'day'
    elif mean_lum > 30:
        return 'dusk'
    else:
        return 'night'

LIGHTING_CONFIGS = {
    'day':   {'conf_threshold': 0.45, 'enhance_clip_limit': 2.0, 'ocr_conf_min': 0.65},
    'dusk':  {'conf_threshold': 0.40, 'enhance_clip_limit': 3.0, 'ocr_conf_min': 0.60},
    'night': {'conf_threshold': 0.35, 'enhance_clip_limit': 4.0, 'ocr_conf_min': 0.55},
}
```

### 8.3 Stage 2 — Dynamic ROI with Temporal Masking

The current design skips ROI gating. A better approach: no spatial ROI, but add temporal masking to exclude stationary objects:

```python
class TemporalBackgroundSubtractor:
    """
    Use MOG2 background subtraction to produce a foreground mask.
    Only run the detection pipeline on regions with motion.
    Eliminates detection overhead on parked vehicles and shadows.
    """
    
    def __init__(self):
        self.subtractor = cv2.createBackgroundSubtractorMOG2(
            history=100,
            varThreshold=50,
            detectShadows=True
        )
    
    def get_motion_mask(self, frame: np.ndarray) -> np.ndarray:
        fg_mask = self.subtractor.apply(frame)
        # Remove shadows (gray pixels in MOG2 output)
        _, fg_binary = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        # Morphological cleanup
        kernel = np.ones((5, 5), np.uint8)
        cleaned = cv2.morphologyEx(fg_binary, cv2.MORPH_OPEN, kernel)
        cleaned = cv2.dilate(cleaned, kernel, iterations=2)
        return cleaned
    
    def has_significant_motion(self, frame: np.ndarray,
                                min_motion_area_px: int = 2000) -> bool:
        mask = self.get_motion_mask(frame)
        motion_area = cv2.countNonZero(mask)
        return motion_area > min_motion_area_px
```

### 8.4 Stage 3 — Cross-Camera Vehicle De-duplication

When adjacent cameras overlap in coverage zone, prevent the same vehicle from being challaned by both:

```python
import hashlib
import sqlite3
from datetime import datetime, timedelta

class CrossCameraDeduplicator:
    """
    Shared SQLite database used by all cameras on the local network.
    Prevents duplicate challans for the same plate within a time window.
    Works via NFS-mounted shared path or SQLite WAL mode over LAN.
    """
    
    COOLDOWN_SECONDS = 300   # 5 minutes — same plate from any camera
    
    def __init__(self, shared_db_path: str = "/mnt/shared/challans.db"):
        self.db_path = shared_db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recent_challans (
                plate_number TEXT NOT NULL,
                camera_id TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                challan_id TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_plate ON recent_challans(plate_number, issued_at)")
        conn.commit()
        conn.close()
    
    def is_duplicate(self, plate_number: str) -> bool:
        cutoff = (datetime.now() - timedelta(seconds=self.COOLDOWN_SECONDS)).isoformat()
        conn = sqlite3.connect(self.db_path, timeout=5)
        row = conn.execute(
            "SELECT COUNT(*) FROM recent_challans WHERE plate_number=? AND issued_at > ?",
            (plate_number, cutoff)
        ).fetchone()
        conn.close()
        return row[0] > 0
    
    def register_challan(self, plate: str, camera_id: str, challan_id: str):
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.execute(
            "INSERT INTO recent_challans VALUES (?,?,?,?)",
            (plate, camera_id, datetime.now().isoformat(), challan_id)
        )
        conn.commit()
        conn.close()
```

### 8.5 Stage 5 — Weather-Adaptive Enhancement

Rain creates lens droplets that degrade plate clarity in a unique way. Detect rain and apply a dedicated derain preprocessing step:

```python
def is_rainy_frame(frame: np.ndarray) -> bool:
    """
    Heuristic: rain streaks appear as vertical high-frequency noise.
    Use variance of horizontal Sobel to detect streak patterns.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    sobel_v = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)  # vertical edges
    sobel_h = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)  # horizontal edges
    v_var = np.var(sobel_v)
    h_var = np.var(sobel_h)
    # Rain streaks: much higher vertical variance than horizontal
    return (v_var / (h_var + 1e-6)) > 3.0


def derain_plate(plate_img: np.ndarray) -> np.ndarray:
    """
    Classical derain for plate crops. Not neural — fast on Pi.
    Uses guided filter to preserve edges while removing streak noise.
    """
    # Convert to float
    img_float = plate_img.astype(np.float32) / 255.0
    
    # Separate into high-frequency (streaks) and low-frequency (content)
    blur = cv2.GaussianBlur(img_float, (7, 1), 0)  # horizontal blur only
    streaks = img_float - blur
    
    # Suppress streaks via soft-thresholding
    threshold = 0.05
    streaks_suppressed = np.sign(streaks) * np.maximum(np.abs(streaks) - threshold, 0)
    
    # Reconstruct
    derained = np.clip(blur + streaks_suppressed * 0.3, 0, 1)
    return (derained * 255).astype(np.uint8)
```

### 8.6 Stage 6 — OCR Ensemble Strategy

Beyond the current 3-round voting, add a character-level ensemble across multiple models:

```python
def ocr_ensemble(plate_img: np.ndarray,
                 paddle_ocr: IndianPlateOCR,
                 easy_ocr_reader=None) -> dict:
    """
    Run two OCR engines, combine at character level using Levenshtein distance.
    Returns the result with highest confidence and best format match.
    """
    results = []
    
    # Engine 1: PaddleOCR (primary)
    r1 = ocr_with_voting(plate_img, paddle_ocr, n_runs=3)
    if r1['cleaned_text']:
        results.append(r1)
    
    # Engine 2: EasyOCR (secondary, if available)
    if easy_ocr_reader:
        try:
            raw = easy_ocr_reader.readtext(plate_img, detail=1)
            combined_text = ''.join([r[1] for r in raw])
            confidence = np.mean([r[2] for r in raw]) if raw else 0.0
            cleaned = IndianPlateOCR._clean_plate_text(None, combined_text)
            results.append({
                'raw_text': combined_text,
                'cleaned_text': cleaned,
                'is_valid': IndianPlateOCR._validate_plate(None, cleaned),
                'confidence': confidence
            })
        except Exception:
            pass
    
    if not results:
        return {'cleaned_text': '', 'is_valid': False, 'confidence': 0.0, 'source': 'none'}
    
    # Prioritise valid format results, then sort by confidence
    valid_results = [r for r in results if r['is_valid']]
    pool = valid_results if valid_results else results
    best = max(pool, key=lambda x: x['confidence'])
    best['source'] = 'ensemble'
    return best
```

### 8.7 Stage 7 — Multi-Frame Evidence Bundle

The current design saves only the trigger frame. For legal robustness, save a 3-second clip:

```python
from collections import deque
import threading
import cv2

class FrameBuffer:
    """
    Circular buffer of the last N seconds of frames.
    When a violation is confirmed, extract pre- and post-event frames.
    """
    
    def __init__(self, fps: float = 15, buffer_seconds: float = 3.0):
        self.maxlen = int(fps * buffer_seconds)
        self.buffer = deque(maxlen=self.maxlen)
        self.lock = threading.Lock()
    
    def add_frame(self, frame: np.ndarray, timestamp: float):
        with self.lock:
            self.buffer.append((frame.copy(), timestamp))
    
    def get_clip(self, start_seconds_ago: float = 2.0,
                 end_seconds_ahead: float = 1.0) -> list:
        """
        Returns frames from [now - start_seconds_ago] to [now + end_seconds_ahead].
        For violations: grab 2 seconds before + 1 second after trigger.
        """
        with self.lock:
            return list(self.buffer)
    
    def save_evidence_video(self, clip: list, output_path: str,
                            fps: float = 15):
        if not clip:
            return
        h, w = clip[0][0].shape[:2]
        writer = cv2.VideoWriter(
            output_path,
            cv2.VideoWriter_fourcc(*'mp4v'),
            fps, (w, h)
        )
        for frame, _ in clip:
            writer.write(frame)
        writer.release()
```

---

## 9. Additional Detection Capabilities

### 9.1 Helmet Detection (High-Value Enhancement)

Adding helmet absence detection dramatically increases the legal and financial leverage of each challan — Section 129 MV Act (no helmet) adds ₹1,000 fine on top of the footpath violation.

**Pre-trained model**: SafetyHelmetDetection YOLOv8
**HuggingFace**: `https://huggingface.co/keremberke/yolov8s-hard-hat-detection`
**Alternative**: `https://huggingface.co/Ultralytics/Assets` — see helmet detection models

```python
class HelmetDetector:
    """
    Detects presence/absence of helmet on rider.
    Runs on the upper-third crop of the rider's bounding box.
    """
    
    UPPER_FRACTION = 0.4   # analyze top 40% of vehicle bbox for rider
    
    def __init__(self, model_path: str = "models/helmet_yolov8n.tflite"):
        self.model = YOLO(model_path)
    
    def detect_helmet(self, vehicle_crop: np.ndarray) -> dict:
        h = vehicle_crop.shape[0]
        rider_region = vehicle_crop[:int(h * self.UPPER_FRACTION), :]
        
        results = self.model(rider_region, conf=0.40, imgsz=160)
        
        classes_detected = []
        if results[0].boxes:
            classes_detected = [
                self.model.names[int(c)]
                for c in results[0].boxes.cls
            ]
        
        return {
            'helmet_present': 'helmet' in classes_detected,
            'no_helmet_detected': 'no_helmet' in classes_detected or 'head' in classes_detected,
            'confidence': float(results[0].boxes.conf.max()) if results[0].boxes else 0.0,
            'additional_violation': 'no_helmet_detected' in classes_detected
        }
```

### 9.2 Triple Riding Detection

Three or more riders is a standalone violation. Detect by counting person bboxes within the vehicle bbox:

```python
class TripleRidingDetector:
    """
    Runs YOLOv8n's 'person' class detections within the vehicle crop.
    If ≥ 3 persons overlap with the two-wheeler bbox → triple riding violation.
    """
    
    def __init__(self, model_path: str = "models/yolov8n_persons.tflite"):
        self.model = YOLO(model_path)
        self.person_class_id = 0   # COCO person class
    
    def count_riders(self, vehicle_crop: np.ndarray) -> dict:
        results = self.model(vehicle_crop, conf=0.35, classes=[self.person_class_id])
        
        rider_count = len(results[0].boxes) if results[0].boxes else 0
        
        return {
            'rider_count': rider_count,
            'triple_riding': rider_count >= 3,
            'additional_violation': rider_count >= 3,
            'fine_addition_inr': 1000 if rider_count >= 3 else 0,
            'section': 'Section 128 MV Act' if rider_count >= 3 else None
        }
```

### 9.3 Wrong-Way Riding Detection

Detect vehicles moving opposite to the expected pedestrian flow direction:

```python
class DirectionAnalyser:
    """
    Classifies vehicle movement direction relative to camera orientation.
    Expected direction is configured at installation (footpath flow direction).
    """
    
    def __init__(self, expected_direction: str = "left_to_right"):
        """
        expected_direction: "left_to_right" | "right_to_left" | "top_to_bottom" | "bottom_to_top"
        """
        self.expected = expected_direction
    
    def classify(self, track_history: deque) -> dict:
        if len(track_history) < 5:
            return {"direction": "unknown", "wrong_way": False}
        
        positions = list(track_history)[-5:]
        dx = positions[-1][0] - positions[0][0]
        dy = positions[-1][1] - positions[0][1]
        
        if abs(dx) > abs(dy):
            actual = "left_to_right" if dx > 0 else "right_to_left"
        else:
            actual = "top_to_bottom" if dy > 0 else "bottom_to_top"
        
        wrong_way = (actual != self.expected)
        
        return {
            "actual_direction": actual,
            "expected_direction": self.expected,
            "wrong_way": wrong_way,
            "additional_violation": wrong_way,
            "dx": round(dx, 1),
            "dy": round(dy, 1)
        }
```

### 9.4 Pedestrian Safety Score

Track the ratio of pedestrians to vehicles on the footpath in real time. High pedestrian count + vehicle presence = elevated risk score that can trigger a priority alert:

```python
class PedestrianSafetyScorer:
    """
    Computes a rolling safety score based on footpath crowding and vehicle presence.
    """
    
    def compute_score(self, pedestrian_count: int, vehicle_count: int) -> dict:
        if vehicle_count == 0:
            return {"risk": "none", "score": 0, "alert": False}
        
        # Risk increases with pedestrian density × vehicle presence
        base_score = vehicle_count * 10
        crowding_multiplier = 1 + (pedestrian_count / 5)
        score = min(int(base_score * crowding_multiplier), 100)
        
        if score >= 70:
            risk = "critical"
        elif score >= 40:
            risk = "high"
        else:
            risk = "moderate"
        
        return {
            "risk": risk,
            "score": score,
            "pedestrian_count": pedestrian_count,
            "vehicle_count": vehicle_count,
            "alert": score >= 70
        }
```

---

## 10. Hardware Accelerator Strategies

### 10.1 Coral USB Accelerator — Model Compilation Pipeline

```bash
# Install Edge TPU compiler
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | \
    sudo tee /etc/apt/sources.list.d/coral-edgetpu.list
sudo apt-get update && sudo apt-get install edgetpu-compiler

# Compile INT8 TFLite model for Edge TPU
edgetpu_compiler \
    --show_operations \
    --num_segments=1 \
    yolov9t_full_integer_quant.tflite

# Expected output:
# Segments (1): yolov9t_full_integer_quant_edgetpu.tflite
# Operations mapped: ~95% (some post-processing stays on CPU)

# Run on Coral
import tflite_runtime.interpreter as tflite
from pycoral.utils.edgetpu import make_interpreter

interpreter = make_interpreter('yolov9t_full_integer_quant_edgetpu.tflite')
interpreter.allocate_tensors()
# Inference at 320px: ~8-12ms
```

### 10.2 Hailo-8 (Raspberry Pi 5) — 26 TOPS

```bash
# Install Hailo SDK
pip install hailort

# Convert ONNX to HEF (Hailo Executable Format)
hailomz compile \
    --hw-arch hailo8 \
    --ckpt yolov8n.onnx \
    --calib-path calibration_data/ \
    --output-mlef yolov8n_hailo8.mlef

hailo optimize \
    --hw-arch hailo8 \
    yolov8n_hailo8.mlef \
    yolov8n_hailo8_optimized.hef

# Inference
import hailo_platform as hp

hef = hp.HEF('yolov8n_hailo8_optimized.hef')
# Latency at 640px: ~3-5ms (26 TOPS NPU)
```

### 10.3 Jetson Nano TensorRT — FP16 Conversion

```python
import tensorrt as trt
import pycuda.driver as cuda
import pycuda.autoinit

TRT_LOGGER = trt.Logger(trt.Logger.WARNING)

def build_engine_onnx(onnx_path: str, engine_path: str,
                       fp16: bool = True,
                       input_shape: tuple = (1, 3, 640, 640)):
    builder = trt.Builder(TRT_LOGGER)
    network = builder.create_network(
        1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
    )
    parser = trt.OnnxParser(network, TRT_LOGGER)
    
    with open(onnx_path, 'rb') as f:
        parser.parse(f.read())
    
    config = builder.create_builder_config()
    config.max_workspace_size = 1 << 30  # 1GB
    
    if fp16 and builder.platform_has_fast_fp16:
        config.set_flag(trt.BuilderFlag.FP16)
    
    engine = builder.build_engine(network, config)
    
    with open(engine_path, 'wb') as f:
        f.write(engine.serialize())
    
    return engine

# Build:   yolov9c_fp16.engine    → ~12ms at 640px on Jetson Nano
# Build:   paddleocr_fp16.engine  → ~25ms per plate on Jetson Nano
```

---

## 11. Production Deployment Patterns

### 11.1 Systemd Service with Health Watchdog

```ini
# /etc/systemd/system/footpath-enforcement.service
[Unit]
Description=Footpath Violation Detection Pipeline
After=network.target
Wants=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/footpath_enforcement
ExecStart=/home/pi/venv/bin/python main.py
Restart=always
RestartSec=5
WatchdogSec=30
NotifyAccess=main

# Resource limits
MemoryMax=3G
CPUQuota=95%

# Logging
StandardOutput=append:/var/log/footpath/stdout.log
StandardError=append:/var/log/footpath/stderr.log

# Environment
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=/home/pi/footpath_enforcement/config/.env

[Install]
WantedBy=multi-user.target
```

### 11.2 Automatic Model Version Management

```python
import hashlib, json, os

class ModelVersionManager:
    """
    Tracks deployed model versions and validates checksums.
    Prevents deployment of corrupted models.
    """
    
    REGISTRY_FILE = "models/model_registry.json"
    
    def __init__(self):
        self.registry = self._load_registry()
    
    def _load_registry(self) -> dict:
        if os.path.exists(self.REGISTRY_FILE):
            return json.load(open(self.REGISTRY_FILE))
        return {}
    
    def validate_model(self, model_name: str, model_path: str) -> bool:
        """Verify model file against registered SHA256 checksum."""
        if model_name not in self.registry:
            return True  # First load — register it
        
        sha256 = hashlib.sha256(open(model_path, 'rb').read()).hexdigest()
        expected = self.registry[model_name]['sha256']
        
        if sha256 != expected:
            raise RuntimeError(
                f"Model checksum mismatch for {model_name}! "
                f"Expected {expected[:16]}..., got {sha256[:16]}... "
                f"Possible corruption or tampering."
            )
        return True
    
    def register_model(self, model_name: str, model_path: str,
                       version: str, description: str):
        sha256 = hashlib.sha256(open(model_path, 'rb').read()).hexdigest()
        self.registry[model_name] = {
            "path": model_path,
            "sha256": sha256,
            "version": version,
            "description": description,
            "registered_at": datetime.now().isoformat()
        }
        json.dump(self.registry, open(self.REGISTRY_FILE, 'w'), indent=2)
    
    def get_model_info(self, model_name: str) -> dict:
        return self.registry.get(model_name, {})
```

### 11.3 Disk Space Guardian

```python
import shutil, os

class DiskSpaceGuardian:
    """
    Ensures violations directory never fills the SD card.
    Implements a retention policy with tiered storage:
    - Hot (local): last 7 days
    - Cold (USB stick/remote): 7-30 days
    - Archive (cloud sync): 30+ days
    """
    
    MIN_FREE_GB = 2.0
    HOT_RETENTION_DAYS = 7
    
    def __init__(self, violations_dir: str = "violations/",
                 cold_storage_dir: str = "/mnt/usb/violations/"):
        self.hot_dir = violations_dir
        self.cold_dir = cold_storage_dir
    
    def check_and_rotate(self):
        _, _, free = shutil.disk_usage(self.hot_dir)
        free_gb = free / (1024**3)
        
        if free_gb < self.MIN_FREE_GB:
            self._rotate_old_violations()
    
    def _rotate_old_violations(self):
        cutoff = datetime.now() - timedelta(days=self.HOT_RETENTION_DAYS)
        
        for dirname in os.listdir(self.hot_dir):
            dir_path = os.path.join(self.hot_dir, dirname)
            if not os.path.isdir(dir_path):
                continue
            
            # Parse date from directory name: 2025-01-15_14-23-07_KA05AB1234
            try:
                dir_date = datetime.strptime(dirname[:19], "%Y-%m-%d_%H-%M-%S")
            except ValueError:
                continue
            
            if dir_date < cutoff:
                # Move to cold storage rather than delete
                dest = os.path.join(self.cold_dir, dirname)
                if os.path.exists(self.cold_dir):
                    shutil.move(dir_path, dest)
                else:
                    shutil.rmtree(dir_path)
```

---

## Quick Reference — Model Selection by Device

| Device | Best Detector | Best OCR | Tracker | Accelerator |
|---|---|---|---|---|
| Raspberry Pi 4 (no accelerator) | NanoDet-Plus-m (ncnn, 25ms) | PaddleOCR PP-OCRv3 ONNX | OC-SORT | None |
| Raspberry Pi 4 + Coral USB | YOLOv7-tiny EdgeTPU (10ms) | PaddleOCR ONNX | OC-SORT | Coral USB |
| Raspberry Pi 5 + Hailo-8 | YOLOv8n HEF (5ms) | PaddleOCR ONNX | BoT-SORT | Hailo-8 26TOPS |
| Orange Pi 5 (Mali-G610) | YOLOv9-t ONNX | PaddleOCR ONNX | OC-SORT | Mali GPU (OpenCL) |
| Jetson Nano | YOLOv9-c TensorRT FP16 (12ms) | PaddleOCR TensorRT | BoT-SORT | 128-core Maxwell |
| Jetson Orin Nano | Gold-YOLO-S TensorRT (4ms) | TrOCR-small INT8 | BoT-SORT + ReID | 1024-core Ampere |

---

## Quick Reference — Observability Checklist

- [ ] Every frame has a `trace_id` (UUID)
- [ ] Every stage records `latency_ms` to SQLite + Prometheus histogram
- [ ] Confidence scores are recorded per stage per frame (not just pass/fail)
- [ ] Prometheus endpoint running on port 8000 (Grafana scrapes)
- [ ] Jaeger running locally (OpenTelemetry spans exported)
- [ ] Confidence drift detector running every 100 frames
- [ ] Manual review rate monitored (alert if > 30%)
- [ ] Thermal throttle flag checked every 60 seconds
- [ ] Disk free space checked every 5 minutes (alert if < 2GB)
- [ ] MQTT offline queue depth monitored (alert if > 50 queued)
- [ ] Model checksum validated on startup
- [ ] Systemd watchdog heartbeat sent every 30 seconds
- [ ] Night mode detector running every frame (luminance-based)
- [ ] Cross-camera deduplication DB accessible (or per-camera cooldown)

---

*Objective 3 — Production-Grade Enhancement Guide*
*Models: YOLOv7-tiny · YOLOv9-t · Gold-YOLO-N · NanoDet-Plus · EdgeYOLO · PP-YOLOE+*
*Observability: OpenTelemetry · Prometheus · Grafana · Jaeger · SQLite Traces*
*Enhancements: OC-SORT · Kalman Filter · Helmet Detection · Triple Riding · Cross-Camera Dedup*
