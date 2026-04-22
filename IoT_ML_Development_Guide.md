# IoT ML Development Guide
## AI-Powered Predictive Crossing Assistant for Vulnerable Pedestrians Using Edge Technology

> **System Philosophy:** Every byte of computation in this system happens on-device. No frame leaves the edge unit. No model call hits the cloud. Every model is chosen specifically because it fits within the RAM, storage, and latency constraints of a Raspberry Pi 4 (4GB) or NVIDIA Jetson Nano (4GB). If a model is too large, too slow, or too dependency-heavy to run on these boards, it is not used — regardless of its accuracy on benchmarks.

---

## Table of Contents

1. [Project Overview & Core Problem](#1-project-overview--core-problem)
2. [System Architecture — All Three Objectives](#2-system-architecture--all-three-objectives)
3. [Edge Device Specification & Constraints](#3-edge-device-specification--constraints)
4. [Objective 1 — Human-Aware Predictive Crossing Intelligence](#4-objective-1--human-aware-predictive-crossing-intelligence)
5. [Objective 2 — Smart Mobility Stick for Visually Impaired](#5-objective-2--smart-mobility-stick-for-visually-impaired)
6. [Objective 3 — Footpath Violation Detection & Auto-Enforcement](#6-objective-3--footpath-violation-detection--auto-enforcement)
7. [All Datasets — Complete Curated Master List](#7-all-datasets--complete-curated-master-list)
8. [All Models — Edge Device Master Reference Table](#8-all-models--edge-device-master-reference-table)
9. [Environment Setup — Training Machine](#9-environment-setup--training-machine)
10. [Edge Conversion — Complete Pipeline](#10-edge-conversion--complete-pipeline)
11. [Evaluation & Acceptance Criteria — All Objectives](#11-evaluation--acceptance-criteria--all-objectives)
12. [Production Deployment Architecture](#12-production-deployment-architecture)
13. [Development Timeline — All Three Objectives](#13-development-timeline--all-three-objectives)
14. [Critical Success Factors & Final Specifications](#14-critical-success-factors--final-specifications)

---

## 1. Project Overview & Core Problem

### What Is Being Built

This is an **Edge AI Pedestrian Safety Intelligence System** that augments existing Vehicle Actuated Control (VAC) infrastructure with human-aware intelligence. The system integrates three fully independent subsystems, each solving a specific class of urban pedestrian hazard, all running on commodity ARM-based edge hardware without any cloud connectivity.

### The Core Problems Being Solved

**Problem 1 — Signal Blindness to Pedestrian Vulnerability:**
Current traffic signals are purely vehicle-centric. A signal timing algorithm does not know whether the people crossing are children, elderly citizens, wheelchair users, or visually impaired individuals. It allocates the same crossing time to everyone. A 75-year-old with a walker gets the same 25 seconds as a healthy adult. This causes mid-crossing stalling incidents, near-miss collisions, and preventable fatalities.

**Problem 2 — Visually Impaired Pedestrians Have No Real-Time Road Intelligence:**
Existing assistive technology for blind pedestrians is either passive (white cane detecting ground-level objects only) or infrastructure-dependent (auditory signals at marked crossings only). There is no portable, intelligent, predictive device that tells a visually impaired person whether it is safe to cross *right now* based on live traffic analysis — especially at unmarked crossings and non-signalised zones.

**Problem 3 — Footpath Encroachment Is Unenforceable at Scale:**
Two-wheelers (motorcycles, scooters, bicycles) routinely use pedestrian footpaths in Indian cities. Manual policing is inadequate. There is no automated system that can continuously monitor footpaths, identify violators, extract evidence, and generate penalty notices without human intervention.

### Innovation Summary

| Innovation | Description |
|---|---|
| **Vulnerable Priority Index (VPI)** | A mathematically defined score `VPI = Σ(weight × count)` that assigns weighted vulnerability scores to detected pedestrian types and dynamically adjusts signal timers. Novel — no existing VAC system implements this. |
| **Predictive Crossing Probability** | `Risk = α×(1/TTC) + β×VulnerableScore + γ×Density + δ×(1−Visibility)` transforms crossing from reactive to data-driven. |
| **Personalized Mobility Modeling** | Walking speed adapted per individual via IMU data — not assumed uniform. |
| **Edge-First Architecture** | Complete pipeline on-device. `<100ms` latency. Zero cloud. Works offline. |
| **Automated e-Challan Generation** | Footpath violations automatically produce geo-tagged, photo-evidenced penalty notices. |

---

## 2. System Architecture — All Three Objectives

### How the Three Objectives Relate

All three objectives run on the **same hardware platform** (Raspberry Pi 4 / Jetson Nano) and share the **same base detection model** (YOLOv8n). This design minimises the total number of models that need to be trained and deployed. Where possible, a single model instance serves multiple objectives simultaneously.

```
SHARED HARDWARE PLATFORM
Raspberry Pi 4 (4GB) / NVIDIA Jetson Nano (4GB)
         |
         ├── [Camera 1: Intersection camera]
         │        └── OBJECTIVE 1: Crossing Intelligence & VPI
         │
         ├── [Camera 2: Wearable stick camera]
         │        └── OBJECTIVE 2: Smart Mobility Stick
         │
         └── [Camera 3: Footpath-mounted camera]
                  └── OBJECTIVE 3: Footpath Violation & OCR
```

### Top-Level Pipeline — All Three Objectives

| Objective | Input | Core ML Stack | Output |
|---|---|---|---|
| **Obj 1: Crossing Intelligence** | 1080p intersection camera RTSP stream | YOLOv8n + MTCNN + SSR-Net + MobileNetV3-Small | GPIO signal extension +10/+20/+30s + wearable BLE alert |
| **Obj 2: Smart Mobility Stick** | Pi Camera Module (wearable, stick-mounted) | YOLOv8n + MobileNetV3-Small + TTC engine | Haptic vibration + bone-conduction audio alerts |
| **Obj 3: Footpath Enforcement** | 1080p footpath IP camera | YOLOv8n + ByteTrack + YOLOv8n-LP + PaddleOCR | e-Challan JSON + photo evidence + MQTT push |

### Model Sharing Strategy

```
yolov8n_base.tflite (3.2 MB)
    ├── Used by Obj 1: detects person, vehicle, wheelchair, cane
    ├── Used by Obj 2: detects vehicle, obstacle, person (same binary)
    └── Used by Obj 3: detects motorcycle, bicycle, scooter
          (separate fine-tuned binary for best accuracy)

mobilenet_v3_small.tflite (4.5 MB)
    ├── Used by Obj 1: 5-class vulnerability classifier (body crop)
    └── Used by Obj 2: 3-class traffic signal classifier (red/green/yellow)
          (separate fine-tuned binary, different final layer)
```

---

## 3. Edge Device Specification & Constraints

### Why These Devices Were Chosen

The entire ML pipeline is designed around two specific boards. Every model architecture choice, every quantisation decision, and every input resolution is driven by what these boards can execute within the required latency budget.

### Primary Edge Device: Raspberry Pi 4 (4GB)

| Specification | Value |
|---|---|
| CPU | Broadcom BCM2711 — Quad-core Cortex-A72 @ 1.8 GHz |
| RAM | 4 GB LPDDR4-3200 |
| GPU | VideoCore VI (no CUDA, no OpenCL compute for ML) |
| Storage | 64 GB microSD + optional USB SSD |
| ML Inference | TFLite runtime with 4 threads (CPU only by default) |
| ML Acceleration | Google Coral USB Accelerator (optional — adds 4 TOPS via USB3) |
| Power Draw | ~3.4W idle, ~6.4W under load |
| Cost | ~₹5,500 |
| **Latency Budget** | **Full pipeline ≤ 200ms** |
| **RAM Budget** | **All models + runtime ≤ 1.8 GB** |
| **Storage Budget** | **All models ≤ 50 MB** |

### Secondary Edge Device: NVIDIA Jetson Nano (4GB)

| Specification | Value |
|---|---|
| CPU | Quad-core ARM Cortex-A57 @ 1.43 GHz |
| GPU | 128-core Maxwell GPU (CUDA 10.2) |
| RAM | 4 GB LPDDR4 (shared CPU+GPU) |
| Storage | 64 GB microSD |
| ML Inference | TFLite INT8 or TensorRT FP16/INT8 |
| ML Acceleration | CUDA + TensorRT (built-in, no extra hardware needed) |
| Power Draw | 5W (5W mode) or 10W (10W mode) |
| Cost | ~₹8,000 |
| **Latency Budget** | **Full pipeline ≤ 100ms** |
| **RAM Budget** | **All models + runtime ≤ 2.5 GB** |

### Absolute Model Size Constraints (Non-Negotiable)

Every model deployed to either device MUST satisfy all three conditions simultaneously:

```
Condition 1: Model file size (TFLite INT8)  ≤  6 MB per model
Condition 2: Runtime RAM footprint          ≤  200 MB per model
Condition 3: Inference latency              ≤  50ms per call (Pi 4, INT8)

Total deployed model storage across ALL objectives: ≤ 50 MB
Total runtime RAM across ALL objectives:             ≤ 1.8 GB (Pi 4)
```

### Why Specific Architectures Were Rejected

| Architecture | Why Rejected |
|---|---|
| YOLOv8s / YOLOv8m | Too slow on Pi 4 — ~200ms+ at 640px. Exceeds latency budget. |
| ResNet-50 classifier | ~100MB model. Exceeds storage budget. ~180ms on Pi 4. |
| EfficientDet-D2 | Complex quantisation. ONNX conversion often fails on ARM. |
| DeepFace (full stack) | Pulls in TF 2.x full runtime. ~700MB RAM footprint. Unusable on Pi. |
| YOLO-NAS | Requires SuperGradients library — not available on ARM TFLite runtime. |
| OpenPose | 200MB+ model. ~2s per frame on Pi 4. |
| Stereo depth models | Require stereo camera hardware not in our hardware budget. |
| Whisper / LLM models | Far outside latency and RAM budgets for any edge use case here. |

---

## 4. Objective 1 — Human-Aware Predictive Crossing Intelligence

### Objective Definition

Deploy an edge-based AI system at signalised road intersections that analyses every pedestrian waiting to cross, determines their vulnerability category (child, adult, elderly, wheelchair user, visually impaired), computes a Vulnerable Priority Index (VPI), and dynamically extends the pedestrian green signal by +10, +20, or +30 seconds based on who is present — all in real time, without cloud connectivity, integrating with the existing VAC (Vehicle Actuated Control) infrastructure via GPIO.

### Why This Objective Exists

Traditional VAC systems extend green time for vehicles (inductance loop detectors in road surface detect vehicle presence). They have zero awareness of pedestrian vulnerability. A school zone at 8 AM with 12 children, two elderly individuals, and one wheelchair user receives the same 25-second crossing window as the same crossing at 2 PM with three adult commuters. This objective changes that.

### The Vulnerable Priority Index — Mathematical Definition

```
VPI = Σ (vulnerability_weight_i × count_i)  for all detected persons i

Where vulnerability weights are:
  adult       = 1   (baseline — no extension triggered)
  child       = 2   (age < 15 years)
  elderly     = 3   (age ≥ 60 years)
  blind       = 4   (detected white cane user)
  wheelchair  = 5   (detected wheelchair or mobility aid user)

Signal extension logic:
  VPI 0–4   → No extension (baseline timer sufficient)
  VPI 5–9   → +10 seconds added to green phase
  VPI 10–14 → +20 seconds added to green phase
  VPI 15+   → +30 seconds added to green phase (maximum)

Example calculation:
  2 children + 1 elderly + 1 wheelchair user present
  VPI = (2×2) + (1×3) + (1×5) = 4 + 3 + 5 = 12
  Result: +20 seconds signal extension
```

### The Complete 7-Stage ML Pipeline

```
[Camera: 1080p IP Camera — RTSP stream at 15-25 FPS]
                    |
                    v
         ┌──────────────────────┐
         │  STAGE 1             │
         │  YOLOv8n (TFLite     │  Input: Full frame 640×640
         │  INT8, 3.2 MB)       │  Output: Person bboxes + Vehicle bboxes
         │  Person & Vehicle    │  Latency: ~15ms (Jetson) / ~55ms (Pi4)
         │  Detection           │  Early exit if 0 persons detected
         └──────────┬───────────┘
                    │
          ┌─────────┴──────────┐
          │  For each person   │
          │  bounding box:     │
          └─────────┬──────────┘
                    │
                    v
         ┌──────────────────────┐
         │  STAGE 2             │
         │  MTCNN (TFLite,      │  Input: Person crop 128×256
         │  1.8 MB)             │  Output: Face bounding box (or None)
         │  Face Detection      │  Latency: ~8ms (Jetson) / ~40ms (Pi4)
         └──────────┬───────────┘
                    │
          ┌─────────┴──────────────────────────┐
          │ Face found?                        │
          │ YES → Stage 3 (age path)           │
          │ NO  → Stage 5 (body path, skip 3)  │
          └─────────┬──────────────────────────┘
                    │
                    v
         ┌──────────────────────┐
         │  STAGE 3             │
         │  SSR-Net (TFLite     │  Input: Face crop 64×64
         │  INT8, ~0.9 MB)      │  Output: Predicted age (0–100)
         │  Age Estimation      │  Latency: ~5ms (Jetson) / ~30ms (Pi4)
         └──────────┬───────────┘
                    │
                    v
         ┌──────────────────────┐
         │  Age-to-Class Rule   │  age < 15  → child  (weight 2)
         │  (no ML — pure code) │  age 15–59 → adult  (weight 1)
         │                      │  age ≥ 60  → elderly (weight 3)
         └──────────┬───────────┘
                    │
                    v
         ┌──────────────────────┐
         │  STAGE 4             │
         │  YOLOv8n fine-tuned  │  Input: Full frame 640×640
         │  (TFLite INT8,       │  Output: wheelchair / white cane /
         │   3.2 MB)            │          crutches bboxes
         │  Assistive Device    │  Latency: ~15ms (Jetson) / ~55ms (Pi4)
         │  Detection           │  (Runs ONCE per frame, not per person)
         └──────────┬───────────┘
                    │
                    v
         ┌──────────────────────┐
         │  STAGE 5             │
         │  MobileNetV3-Small   │  Input: Person crop 224×224
         │  (TFLite INT8,       │  Output: 5-class label + confidence
         │   4.5 MB)            │  Classes: child/adult/elderly/
         │  Vulnerability       │           wheelchair/blind_cane
         │  Classifier          │  Latency: ~10ms (Jetson) / ~25ms (Pi4)
         │  (full-body backup)  │  Used when: no face detected, OR
         │                      │  when device detected in Stage 4
         └──────────┬───────────┘
                    │
                    v
         ┌──────────────────────┐
         │  STAGE 6             │  VPI = Σ(weight × count)
         │  VPI Computation     │  Deterministic Python rule engine
         │  (no ML — pure code) │  Latency: <1ms
         └──────────┬───────────┘
                    │
                    v
         ┌──────────────────────┐
         │  STAGE 7             │  GPIO output to traffic controller
         │  Signal Extension    │  +10s / +20s / +30s relay trigger
         │  Controller          │  Simultaneous BLE broadcast to
         │                      │  wearable devices (ESP32)
         └──────────────────────┘
```

### Stage 1 — YOLOv8n Person & Vehicle Detector

**Why YOLOv8n specifically:**

YOLOv8n (Nano) is the smallest member of the Ultralytics YOLOv8 family. At 3.2 MB in TFLite INT8 format, it is the largest model that can achieve the required detection quality while staying within the Pi 4 compute budget. The YOLOv8 architecture has native TFLite INT8 export with full NMS baked into the graph, meaning no separate post-processing code is needed on the Pi.

The pretrained COCO weights give a strong baseline for `person`, `bicycle`, `motorcycle`, `car`, `bus`, `truck` — all relevant classes for this system — before any fine-tuning begins.

**Detection classes for Objective 1:**

```
Class 0: person         (all pedestrians)
Class 1: wheelchair     (added via fine-tuning)
Class 2: white_cane     (added via fine-tuning)
Class 3: bicycle
Class 4: motorcycle
Class 5: car
Class 6: bus
Class 7: truck
```

**Training configuration:**

```bash
yolo detect train \
    model=yolov8n.pt \
    data=datasets/pedestrian_vehicles/data.yaml \
    epochs=100 \
    imgsz=640 \
    batch=32 \
    device=0 \
    workers=8 \
    project=runs/obj1 \
    name=pedestrian_v1 \
    pretrained=True \
    optimizer=AdamW \
    lr0=0.001 \
    weight_decay=0.0005 \
    mosaic=1.0 \
    flipud=0.1 \
    degrees=5.0

# Target: mAP50 > 0.75 for person class
# Target: mAP50 > 0.80 for vehicle classes
```

**Edge export:**

```python
from ultralytics import YOLO
model = YOLO("runs/obj1/pedestrian_v1/weights/best.pt")
model.export(
    format="tflite",
    int8=True,
    data="datasets/pedestrian_vehicles/data.yaml",
    imgsz=320,    # 320px for Pi 4; use 640px for Jetson
    simplify=True,
    nms=True,
)
# Output: best_int8.tflite (~3.2 MB)
```

### Stage 2 — MTCNN Face Detector

**Why MTCNN over other face detectors:**

MTCNN (Multi-task Cascaded Convolutional Networks) is a cascade of three tiny CNNs (P-Net, R-Net, O-Net). This cascade design means fast rejection of non-face regions in the first stage, so the full network rarely runs on background patches. At 1.8 MB TFLite, it achieves recall comparable to RetinaFace at roughly half the latency on ARM.

**Why NOT RetinaFace:** RetinaFace requires the insightface library which has a heavy dependency chain on ARM. MTCNN via `facenet-pytorch` exports cleanly to TFLite with no C++ extensions.

**Why NOT OpenCV haarcascade:** Unacceptable false positive rate in outdoor scenes with complex backgrounds like intersections. Often triggers on patterns in signage, foliage, and shadows.

**Key design decision — dual-path fallback:**

```
Person crop received
        |
   Run MTCNN face detector
        |
   Face found (≥ 64px width)?
   ├── YES → crop face → run SSR-Net age estimation → classify
   └── NO  → run full-body MobileNetV3 classifier instead
              (person facing away, too far, occluded)
```

The dual-path design is critical for real-world robustness. In street scenes, 30–40% of persons will be facing away from the camera or have their face obscured. The system cannot fail or skip these persons — they may be children or elderly.

**Code:**

```python
from facenet_pytorch import MTCNN
import torch

device = torch.device('cpu')  # always CPU on Pi 4
mtcnn = MTCNN(
    image_size=64,
    margin=20,
    min_face_size=20,    # minimum face size in pixels — set low for distant persons
    device=device,
    keep_all=True,
    select_largest=False,
)

def detect_face(person_crop):
    boxes, probs = mtcnn.detect(person_crop)
    if boxes is None or len(boxes) == 0:
        return None   # trigger fallback to body classifier
    # Filter by minimum confidence
    valid = [(b, p) for b, p in zip(boxes, probs) if p > 0.90]
    if not valid:
        return None
    return valid[0][0]  # return highest-confidence face box
```

### Stage 3 — SSR-Net Age Estimator

**Why SSR-Net specifically:**

SSR-Net (Soft Stagewise Regression Network) was designed explicitly for age estimation at minimal model size. At ~1 MB TFLite INT8, it achieves Mean Absolute Error (MAE) of approximately 3.1 years on the MORPH-II benchmark and ~4.8 years on the UTKFace test set. This accuracy is more than sufficient for the three-class task (child/adult/elderly) where class boundaries are at 15 and 60 years.

**Why NOT MobileNet-regression for age:** A MobileNetV3 with a regression head is 4× larger (~4.5 MB) and 3× slower on Pi 4 than SSR-Net, for comparable or worse age MAE performance in the sub-20-year and 60+ year ranges where our classification boundaries lie.

**Why NOT DeepFace age model:** DeepFace bundles the full TensorFlow Keras runtime including VGG-Face (~550 MB). This alone exceeds the Pi 4 RAM budget and is categorically unusable on any edge device in this project.

**Training SSR-Net on UTKFace:**

```bash
git clone https://github.com/shamangary/SSR-Net.git
cd SSR-Net

# UTKFace image filenames encode age: [age]_[gender]_[race]_[timestamp].jpg
# No separate label file needed — parse from filename

python training/train_ssrnet.py \
    --data_dir datasets/utkface/crop_part1 \
    --epochs 80 \
    --batch_size 64 \
    --lr 0.001 \
    --model_name ssrnet_pedestrian

# Target: MAE < 5 years on UTKFace val set
# If MAE > 7 after 80 epochs, add 20k IMDB-WIKI faces and retrain
```

**Age-to-class conversion (deterministic — no ML):**

```python
def age_to_vulnerability(predicted_age: float) -> tuple[str, int]:
    """
    Convert SSR-Net's raw age output to a VPI class and weight.
    Boundaries chosen based on:
      - 15: legal definition of child in India for road safety
      - 60: WHO definition of older person + Indian senior citizen threshold
    """
    if predicted_age < 15:
        return ('child', 2)
    elif predicted_age >= 60:
        return ('elderly', 3)
    else:
        return ('adult', 1)   # adults get baseline weight — no signal extension
```

### Stage 4 — Assistive Device Detector (YOLOv8n fine-tuned)

This is a **separate fine-tuned instance** of YOLOv8n trained to detect mobility and visual assistance devices. It runs on the full camera frame once per processed frame — not per person. This single pass can detect multiple devices across multiple people simultaneously.

**Why a separate model instead of adding classes to Stage 1:**

The assistive device classes (wheelchair, white cane, crutches) have very few training examples compared to person/vehicle classes. Training them together causes the common classes to dominate the loss and the rare device classes to underfit. Separate fine-tuning with class-weighted loss and extended epochs achieves significantly better mAP on these rare but critical classes.

**Classes:**

```
Class 0: wheelchair      (manual + electric)
Class 1: white_cane      (folded and extended)
Class 2: crutches        (single + pair)
Class 3: walker          (zimmer frame, rollator)
```

**Training configuration:**

```bash
# Download datasets from Roboflow
from roboflow import Roboflow
rf = Roboflow(api_key='YOUR_API_KEY')
project = rf.workspace().project('assistive-devices-detection')
dataset = project.version(1).download('yolov8')

# Fine-tune — longer epochs because dataset is small (~5,000 images)
yolo detect train \
    model=yolov8n.pt \
    data=assistive-devices/data.yaml \
    epochs=150 \
    imgsz=640 \
    batch=16 \
    device=0 \
    name=assistive_v1 \
    augment=True \
    degrees=15.0 \
    flipud=0.3 \
    mosaic=1.0 \
    copy_paste=0.2

# Target: mAP50 > 0.70 (wheelchair), > 0.65 (white cane)
```

### Stage 5 — MobileNetV3-Small Vulnerability Classifier

This is the **core decision classifier** for the entire Objective 1 system. It receives a 224×224 px crop of an individual person and outputs a probability distribution across 5 vulnerability classes. It serves two roles simultaneously:

1. **Primary role:** Full-body fallback when MTCNN finds no face (person facing away, too far, occluded, wearing a mask)
2. **Secondary role:** Confirm or override the assistive device signal from Stage 4 using whole-body context (posture, clothing, body proportions)

**Why MobileNetV3-Small over alternatives:**

| Architecture | Size (INT8) | Latency (Pi4) | Top-1 Accuracy | Decision |
|---|---|---|---|---|
| MobileNetV3-Small | ~4.5 MB | ~25ms | 67.4% (ImageNet) | ✅ **Chosen** |
| MobileNetV2 | ~6.9 MB | ~35ms | 72.0% | Too slow |
| EfficientNet-Lite0 | ~6.0 MB | ~38ms | 75.1% | Too slow |
| ShuffleNetV2 0.5x | ~2.9 MB | ~18ms | 60.6% | Too inaccurate |
| SqueezeNet | ~4.0 MB | ~30ms | 57.5% | Too inaccurate |

MobileNetV3-Small hits the right balance: fast enough for the Pi 4 pipeline budget, accurate enough after fine-tuning on our 5-class vulnerability dataset.

**Two-phase transfer learning:**

```python
import torch
import torchvision.models as models
import torch.nn as nn

# Load pretrained ImageNet weights
model = models.mobilenet_v3_small(weights='IMAGENET1K_V1')

# Replace the final classification layer
# Original: Linear(576, 1000)
# New:      Linear(576, 5)   — 5 vulnerability classes
model.classifier[3] = nn.Linear(model.classifier[3].in_features, 5)

# Class weights compensate for dataset imbalance
# adult class has 6,000 images; blind_cane has only 2,000
class_weights = torch.tensor([1.5, 1.0, 1.5, 2.5, 3.0])
criterion = nn.CrossEntropyLoss(weight=class_weights.to(device))

# PHASE 1: Freeze all backbone layers, train only new classifier head
# Purpose: Warm up the new head without corrupting pretrained features
for param in model.features.parameters():
    param.requires_grad = False

optimizer = torch.optim.AdamW(model.classifier.parameters(), lr=1e-3)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=10)
# Train 10 epochs

# PHASE 2: Unfreeze last 3 feature blocks + classifier, fine-tune everything
for param in model.features[-3:].parameters():
    param.requires_grad = True

optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-4)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=30)
# Train 30 epochs

# Target: Weighted F1 > 0.82 across all 5 classes
```

**Mandatory augmentation strategy:**

All augmentations must simulate real-world intersection camera conditions. Apply with `albumentations`:

```python
import albumentations as A
from albumentations.pytorch import ToTensorV2

train_transforms = A.Compose([
    A.RandomBrightnessContrast(
        brightness_limit=0.4, contrast_limit=0.4, p=0.6
    ),   # simulate dawn / dusk / cloudy / bright sun at intersection
    A.GaussNoise(var_limit=(10, 60), p=0.4),
    # simulate compressed RTSP stream noise and sensor noise at night
    A.HorizontalFlip(p=0.5),
    A.RandomCrop(height=200, width=200, p=0.4),
    A.Resize(224, 224),
    A.Perspective(scale=(0.02, 0.08), p=0.3),
    # simulate elevated camera angle (cameras mounted 3-5m high)
    A.CoarseDropout(
        max_holes=6, max_height=40, max_width=40, p=0.3
    ),   # simulate partial occlusion by other pedestrians
    A.MotionBlur(blur_limit=(3, 9), p=0.2),
    # simulate person walking during frame capture
    A.Normalize(mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]),
    ToTensorV2(),
])
```

### Stage 6 — VPI Computation Engine

This stage requires no machine learning model. It is a deterministic Python function that aggregates all classification results from Stages 3–5 and computes the VPI score.

```python
VPI_WEIGHTS = {
    'adult':       1,
    'child':       2,
    'elderly':     3,
    'blind_cane':  4,
    'wheelchair':  5,
}

VPI_THRESHOLDS = {
    'low':    (5, 10),    # VPI  5–9   → +10 seconds
    'medium': (10, 15),   # VPI 10–14  → +20 seconds
    'high':   (15, 999),  # VPI 15+    → +30 seconds
}

def compute_vpi(detections: list[dict]) -> tuple[int, int]:
    """
    Args:
        detections: list of {'class': str, 'weight': int, 'confidence': float}
                    one entry per detected person/device
    Returns:
        (vpi_score: int, signal_extension_seconds: int)
    """
    # Filter out low-confidence detections
    high_conf = [d for d in detections if d.get('confidence', 1.0) > 0.55]

    vpi = sum(VPI_WEIGHTS.get(d['class'], 0) for d in high_conf)

    if vpi >= 15: return (vpi, 30)
    elif vpi >= 10: return (vpi, 20)
    elif vpi >= 5:  return (vpi, 10)
    else:           return (vpi, 0)
```

### Stage 7 — GPIO Signal Controller

The GPIO controller translates the VPI decision into a physical signal to the traffic controller. This uses the Raspberry Pi's GPIO pins to trigger a relay connected to the existing VAC signal controller's pedestrian extension input.

```python
import RPi.GPIO as GPIO
import time

RELAY_PIN_10S = 17    # GPIO pin for +10s relay
RELAY_PIN_20S = 27    # GPIO pin for +20s relay
RELAY_PIN_30S = 22    # GPIO pin for +30s relay

GPIO.setmode(GPIO.BCM)
GPIO.setup([RELAY_PIN_10S, RELAY_PIN_20S, RELAY_PIN_30S], GPIO.OUT, initial=GPIO.LOW)

def extend_signal(extension_seconds: int):
    """Trigger the appropriate relay to extend the pedestrian green phase."""
    pin_map = {10: RELAY_PIN_10S, 20: RELAY_PIN_20S, 30: RELAY_PIN_30S}
    pin = pin_map.get(extension_seconds)
    if pin:
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(0.5)   # 500ms pulse sufficient for VAC controller
        GPIO.output(pin, GPIO.LOW)
        print(f"[SIGNAL] Extended by +{extension_seconds}s (GPIO pin {pin})")
```

---

## 5. Objective 2 — Smart Mobility Stick for Visually Impaired

### Objective Definition

Design and deploy a wearable AI guidance system integrated into a standard white cane. The system continuously analyses the environment around the user using a compact camera mounted on the stick, detects approaching vehicles, stray animals, road surface hazards, and unsafe crossing gaps, estimates the time-to-collision of approaching vehicles, reads traffic signals, and delivers real-time guidance through haptic vibration and bone-conduction audio — enabling independent, safe navigation beyond marked crossings.

### Why This Objective Exists

The current white cane detects only ground-level obstacles within arm's reach. It provides zero information about approaching vehicles, traffic signal state, or whether a crossing gap is safe to use. Visually impaired pedestrians in Indian cities — where traffic is dense, signals are often non-functional, and footpaths force pedestrians onto carriageways — face disproportionately high collision risk. Existing auditory signal poles cover only a tiny fraction of crossings.

### Hardware Platform for Objective 2

| Component | Specification | Why This Component |
|---|---|---|
| Compute | Raspberry Pi Zero 2W or Raspberry Pi 4 (compact) | Pi Zero 2W: 65g, battery-powered, fits in cane handle; Pi 4: more compute for better accuracy |
| Camera | Pi Camera Module 3 (12MP, autofocus) | Wide-angle, compact, USB or CSI connector |
| IMU | MPU-6050 (I2C) | Detect walking speed, stick angle, fall detection |
| Haptic | ERM vibration motor (3.3V GPIO) | Alert patterns: 1 pulse = caution, 3 rapid = danger |
| Audio | Bone-conduction speaker (3.5mm AUX) | Doesn't block ambient sound — safety critical |
| Battery | Li-ion 3000mAh + BMS | ~4 hours runtime on Pi Zero 2W |
| GPS | NEO-6M (UART) | Location logging + future crossing database |

### The Smart Stick ML Pipeline — 6 Stages

```
[Pi Camera: 640×480 @ 10 FPS (Pi Zero) or 1080p @ 15 FPS (Pi 4)]
                    |
                    v
         ┌──────────────────────┐
         │  STAGE 1             │
         │  YOLOv8n (TFLite     │  Input: 320×320 (Pi Zero) / 640×640 (Pi4)
         │  INT8, 3.2 MB)       │  Detects: car, motorcycle, bus, truck,
         │  Vehicle & Obstacle  │           bicycle, person, animal, pothole
         │  Detection           │  Latency: ~55ms (Pi4) / ~120ms (Pi Zero)
         └──────────┬───────────┘
                    |
                    v
         ┌──────────────────────┐
         │  STAGE 2             │
         │  Monocular Distance  │  Input: Vehicle bounding box width (px)
         │  Estimation          │  Formula: dist = (known_width × focal_len)
         │  (no ML — physics)   │           / bbox_width_px
         │                      │  Output: Distance in metres
         └──────────┬───────────┘
                    |
                    v
         ┌──────────────────────┐
         │  STAGE 3             │
         │  TTC Computation     │  Input: dist_t0, dist_t1, camera fps
         │  (no ML — physics)   │  Formula: TTC = dist / approach_speed
         │                      │  Output: Time-to-collision in seconds
         └──────────┬───────────┘
                    |
                    v
         ┌──────────────────────┐
         │  STAGE 4             │
         │  Traffic Signal      │  Input: Signal crop (if detected)
         │  Classifier          │  Model: MobileNetV3-Small (4.5 MB)
         │  MobileNetV3-Small   │  Classes: red / green / yellow / unknown
         │  (fine-tuned, 3-cls) │  Latency: ~25ms (Pi4)
         └──────────┬───────────┘
                    |
                    v
         ┌──────────────────────┐
         │  STAGE 5             │
         │  Risk Score Engine   │  Risk = α×(1/TTC) + β×VehicleCount
         │  (no ML — formula)   │         + γ×(1−SignalGreen)
         │                      │  Output: risk_level (SAFE/CAUTION/DANGER)
         └──────────┬───────────┘
                    |
                    v
         ┌──────────────────────┐
         │  STAGE 6             │
         │  Alert Generator     │  SAFE   → no alert
         │  (GPIO + pyttsx3)    │  CAUTION → 1 vibration + quiet tone
         │                      │  DANGER → 3 rapid vibrations + voice alert
         └──────────────────────┘
```

### Stage 1 — YOLOv8n Vehicle & Obstacle Detector (Shared with Obj 1)

The same YOLOv8n base architecture is used, but the class list is adapted for the stick-mounted perspective. The camera faces forward at eye/chest height rather than downward from a pole.

**Detection classes for Objective 2:**

```
Class 0: car
Class 1: motorcycle
Class 2: bus
Class 3: truck
Class 4: bicycle
Class 5: person           (pedestrians — relevant for crossing gap estimation)
Class 6: animal           (cows, dogs — extremely common hazard in Indian roads)
Class 7: pothole          (ground hazard — added via fine-tuning)
Class 8: traffic_signal   (to trigger the signal classifier in Stage 4)
```

**Key difference from Objective 1 model:** The camera angle is eye-level, horizontal, rather than elevated and downward-facing. This means the training data perspective must match. The IDD (Indian Driving Dataset) is preferred here because it was collected from a dashcam/eye-level perspective matching the stick camera angle.

**Input resolution choice by device:**

```
Pi Zero 2W: Use 256×256 px input → ~15 FPS on CPU
             Acceptable for TTC estimation (doesn't need high resolution)

Raspberry Pi 4: Use 320×320 px input → ~18 FPS on CPU
                OR use Google Coral USB Accelerator → 640×640 px at ~25 FPS

Jetson Nano: Use 640×640 px input → ~22 FPS
```

### Stage 2 — Monocular Distance Estimation (Physics-Based, No ML)

Without a stereo camera or LiDAR (both are too expensive and heavy for a wearable cane), distance is estimated from the known real-world width of vehicle classes and the observed bounding box width in the camera frame. This is a well-established technique in monocular ADAS systems.

**Camera calibration (done once at manufacturing/setup):**

```python
# Camera calibration — run ONCE during device setup
# Place a known-width object (e.g., 1.8m rope) at known distance (e.g., 5m)
# Measure the pixel width of the rope in the camera frame

FOCAL_LENGTH_PX = (observed_pixel_width × known_distance_m) / known_object_width_m
# Example: (94 px × 5.0 m) / 1.8 m = 261 px focal length

# Save to config
import json
json.dump({"focal_length_px": 261}, open("config/camera_cal.json", "w"))
```

**Distance estimation per vehicle class:**

```python
# Known average widths of Indian road vehicles
VEHICLE_WIDTHS_M = {
    'car':        1.80,
    'motorcycle': 0.80,
    'bus':        2.50,
    'truck':      2.40,
    'bicycle':    0.55,
    'auto':       1.40,
}

def estimate_distance(vehicle_class: str, bbox_width_px: float,
                      focal_length_px: float) -> float:
    """
    Returns estimated distance to vehicle in metres.
    Accuracy: ±25% for 1–20m range (sufficient for TTC alert thresholds).
    """
    known_width = VEHICLE_WIDTHS_M.get(vehicle_class, 1.8)
    if bbox_width_px < 5:
        return float('inf')   # too small to estimate reliably
    return (known_width * focal_length_px) / bbox_width_px
```

### Stage 3 — TTC (Time-to-Collision) Computation

```python
from collections import defaultdict, deque

dist_history = defaultdict(lambda: deque(maxlen=5))

def compute_ttc(track_id: int, current_dist: float, fps: float) -> float:
    """
    Compute Time-to-Collision for a tracked vehicle.
    Uses smoothed approach speed from last N frames.
    Returns TTC in seconds, or +inf if vehicle is stationary/moving away.
    """
    dist_history[track_id].append(current_dist)

    if len(dist_history[track_id]) < 3:
        return float('inf')   # insufficient history

    dists = list(dist_history[track_id])
    # Approach speed = rate of distance decrease (positive = approaching)
    approach_speeds = [(dists[i-1] - dists[i]) * fps
                       for i in range(1, len(dists))]
    avg_speed = sum(approach_speeds) / len(approach_speeds)

    if avg_speed <= 0.1:
        return float('inf')   # not approaching meaningfully

    return dists[-1] / avg_speed   # TTC in seconds

# Alert thresholds (tuned for urban Indian road speeds)
TTC_DANGER  = 3.0   # seconds — loud buzz + "DANGER STOP" voice
TTC_CAUTION = 6.0   # seconds — single vibration + "CAUTION" tone
# TTC > 6s → SAFE — no alert
```

### Stage 4 — Traffic Signal Classifier (MobileNetV3-Small, Fine-Tuned)

This is a dedicated 3-class (4 with Unknown) classification model. It receives a cropped image of a traffic signal (detected by the YOLOv8n Stage 1 model under class `traffic_signal`) and outputs the signal state.

**Why a separate classifier instead of adding signal state to YOLO:**

YOLO outputs bounding box + class but not state. The state (red/green/yellow) is determined by which lamp is illuminated — a subtle visual difference requiring a classifier, not a locator.

**Training:**

```python
# Fine-tune MobileNetV3-Small for 4-class signal recognition
# Same architecture as Objective 1 classifier, different final layer size (4 not 5)

model = models.mobilenet_v3_small(weights='IMAGENET1K_V1')
model.classifier[3] = nn.Linear(model.classifier[3].in_features, 4)
# Classes: 0=red, 1=green, 2=yellow, 3=unknown

# Phase 1: head only, 8 epochs
# Phase 2: unfreeze last 2 blocks, 20 epochs
# Target: accuracy > 93% on LISA val set
#         accuracy > 85% on self-collected Indian signal images
```

**Critical domain adaptation — Indian signal appearance:**

Indian traffic signals use different LED cluster layouts, pole designs, and signal head shapes compared to European/American signals used in LISA and Bosch datasets. After pre-training on LISA (~7,800 images) + Bosch (~13,000 images), **fine-tune for 10–15 additional epochs on 500–1,000 manually collected Indian signal images** (easily collected using a phone at any intersection). This domain adaptation step raises accuracy from ~70% to ~90%+ on Indian signals.

### Stage 5 — Risk Score Engine

```python
def compute_risk(ttc_values: list[float], vehicle_count: int,
                 signal_state: str) -> tuple[str, float]:
    """
    Composite risk scoring for crossing guidance.

    Risk = α×(1/TTC_min) + β×vehicle_count + γ×(1 if not green else 0)

    Alpha, Beta, Gamma are tunable parameters.
    Returns: (risk_level: 'SAFE'|'CAUTION'|'DANGER', risk_score: float)
    """
    ALPHA = 0.5    # TTC dominates
    BETA  = 0.2    # vehicle count matters
    GAMMA = 0.3    # signal state matters

    ttc_min = min((t for t in ttc_values if t != float('inf')),
                  default=float('inf'))

    ttc_component  = ALPHA / ttc_min if ttc_min > 0 else ALPHA * 10
    count_component = BETA * min(vehicle_count, 5) / 5.0
    signal_component = GAMMA if signal_state not in ('green', 'unknown') else 0.0

    risk_score = ttc_component + count_component + signal_component

    if risk_score > 0.6 or ttc_min < 3.0:
        return ('DANGER', risk_score)
    elif risk_score > 0.3 or ttc_min < 6.0:
        return ('CAUTION', risk_score)
    else:
        return ('SAFE', risk_score)
```

---

## 6. Objective 3 — Footpath Violation Detection & Auto-Enforcement

### Objective Definition

Deploy footpath-mounted camera systems that autonomously detect two-wheelers (motorcycles, scooters, bicycles) encroaching on pedestrian footpaths, track their movement, estimate speed, extract the vehicle licence plate via OCR, package geo-tagged photo evidence, and generate an e-Challan notice — all on-device without cloud connectivity.

### The 7-Stage Pipeline

```
[Footpath camera — 1080p, IP66, global shutter preferred]
                    |
                    v
         ┌──────────────────────┐
         │  STAGE 1             │
         │  YOLOv8n fine-tuned  │  Input: 320×320 (Pi4) / 640×640 (Jetson)
         │  Two-Wheeler         │  Classes: motorcycle, bicycle,
         │  Detector            │           e-scooter, scooter
         │  (TFLite INT8)       │  Latency: ~55ms (Pi4) / ~22ms (Jetson)
         └──────────┬───────────┘
                    |
                    v (if vehicle detected)
         ┌──────────────────────┐
         │  STAGE 2             │
         │  ROI Footpath        │  Input: Vehicle bbox + ROI polygon
         │  Boundary Check      │  Logic: cv2.pointPolygonTest
         │  (no ML — geometry)  │  Output: INSIDE_FOOTPATH bool
         └──────────┬───────────┘
                    |
                    v (if inside footpath)
         ┌──────────────────────┐
         │  STAGE 3             │
         │  ByteTrack           │  Input: Detections across frames
         │  Multi-Object        │  Output: Stable track ID + speed km/h
         │  Tracker + Speed     │  Latency: ~5ms (any device)
         └──────────┬───────────┘
                    |
                    v (if speed > 5 km/h — moving violation)
         ┌──────────────────────┐
         │  STAGE 4             │
         │  YOLOv8n-LP          │  Input: Cropped vehicle region
         │  Licence Plate       │  Output: Tight plate bounding box
         │  Localiser           │  Latency: ~40ms (Pi4) / ~18ms (Jetson)
         │  (TFLite INT8)       │
         └──────────┬───────────┘
                    |
                    v
         ┌──────────────────────┐
         │  STAGE 5             │
         │  CLAHE + Unsharp     │  Input: Raw plate crop (often 30–80px wide)
         │  Mask Enhancement    │  Output: Enhanced plate (400px wide)
         │  (OpenCV, CPU-only)  │  Latency: ~8ms (any device)
         │  OR ESRGAN-tiny      │  (ESRGAN: Jetson only, ~25ms)
         └──────────┬───────────┘
                    |
                    v
         ┌──────────────────────┐
         │  STAGE 6             │
         │  PaddleOCR PP-OCRv3  │  Input: Enhanced plate image
         │  (ONNX Runtime)      │  Output: Plate text string
         │  Fine-tuned Indian   │  + regex validation
         │  LP recognition      │  Latency: ~90ms (Pi4) / ~35ms (Jetson)
         └──────────┬───────────┘
                    |
                    v
         ┌──────────────────────┐
         │  STAGE 7             │  Output: e-Challan JSON
         │  Evidence Package    │          Annotated frame
         │  Generator           │          Plate crop images
         │  + MQTT Push         │          Police dashboard alert
         └──────────────────────┘
```

### Stage 1 — YOLOv8n Two-Wheeler Detector

**Classes for Objective 3:**

```
Class 0: motorcycle    (street bikes, delivery bikes, Royal Enfield, Splendor etc.)
Class 1: bicycle       (pedal cycles, cargo bicycles)
Class 2: e-scooter     (Ola S1, Ather, TVS iQube — increasingly common)
Class 3: scooter       (Activa, Jupiter, Access — most common Indian two-wheeler)
Class 4: auto_rickshaw (optional — often stops/parks on footpaths)
```

**Why this needs a separate fine-tuned binary from Objective 1:**

The Objective 1 model has a wide class set optimised for intersection scenes viewed from above. The Objective 3 camera is footpath-mounted at ~3.5–5 metres height, angled downward at 25–35°. This perspective is different enough that fine-tuning specifically on footpath-angle two-wheeler images substantially improves detection accuracy over using the Objective 1 binary directly.

**Confidence threshold:**

```python
# Lower than typical — we want high recall (catch all violations)
# False positives are filtered by subsequent ROI check + speed threshold
CONF_THRESHOLD = 0.40
NMS_IOU = 0.50
MIN_BBOX_AREA_PX = 1500  # ignore tiny distant detections
```

### Stage 2 — ROI Footpath Boundary Check

The Region of Interest polygon defines the footpath boundary in the camera frame. Set once at installation, stored in config JSON. The check is a pure geometric point-in-polygon test using OpenCV — no ML required, executes in under 1ms.

```python
import cv2, json, numpy as np

def load_roi(config_path: str) -> np.ndarray:
    with open(config_path) as f:
        cfg = json.load(f)
    return np.array(cfg["footpath_roi"], dtype=np.int32)

def is_on_footpath(bbox: list, roi: np.ndarray) -> bool:
    """
    Test if the bottom-center point of a vehicle bbox is inside the footpath ROI.
    Using bottom-center (ground contact point) is more accurate than bbox center.
    """
    x1, y1, x2, y2 = [int(v) for v in bbox]
    test_point = (int((x1+x2)/2), int(y2))  # bottom-center
    result = cv2.pointPolygonTest(roi, test_point, False)
    return result >= 0
```

### Stage 3 — ByteTrack + Speed Estimation

ByteTrack is used instead of DeepSORT because it requires no re-identification neural network — it uses IoU-based matching only. This makes it ~10× lighter than DeepSORT on the Pi 4 (5ms vs 50ms per frame).

```python
from ultralytics import YOLO

model = YOLO('models/twowheeler_int8.tflite', task='detect')
results = model.track(
    source=frame,
    persist=True,
    tracker="bytetrack.yaml",
    conf=0.40,
    iou=0.50,
)
# results[0].boxes.id → stable track IDs across frames
```

**Speed estimation:**

```python
from collections import defaultdict, deque
import numpy as np

track_history = defaultdict(lambda: deque(maxlen=10))

def estimate_speed(track_id, center, fps, pixels_per_metre):
    track_history[track_id].append(center)
    if len(track_history[track_id]) < 3:
        return 0.0
    pts = list(track_history[track_id])[-3:]
    dists = [np.hypot(pts[i][0]-pts[i-1][0], pts[i][1]-pts[i-1][1])
             for i in range(1, len(pts))]
    avg_px_frame = np.mean(dists)
    return round(avg_px_frame / pixels_per_metre * fps * 3.6, 1)  # km/h

SPEED_THRESHOLD_KMPH = 5.0  # below = parked vehicle, skip challan
```

### Stage 4 — Licence Plate Localiser (YOLOv8n-LP)

A second fine-tuned YOLOv8n instance trained to detect the licence plate as a tight bounding box within the vehicle crop. Single class: `licence_plate`.

```bash
yolo detect train \
    model=yolov8n.pt \
    data=datasets/lp_localise/data.yaml \
    epochs=200 \
    imgsz=640 \
    batch=32 \
    device=0 \
    name=lp_localise_v1 \
    patience=30 \
    lr0=0.001 \
    mosaic=1.0

# Target: mAP50 > 0.88 (licence_plate)
# Prioritise recall over precision: Recall @ conf=0.3 > 0.92
```

### Stage 5 — Plate Image Enhancement

Classical OpenCV pipeline — no neural network. Runs in ~8ms on Pi 4 CPU.

```python
import cv2, numpy as np

def enhance_plate(plate_img: np.ndarray, target_width=400) -> np.ndarray:
    # Step 1: Bicubic upscale
    h, w = plate_img.shape[:2]
    scale = target_width / w
    up = cv2.resize(plate_img, (target_width, int(h*scale)),
                    interpolation=cv2.INTER_CUBIC)
    # Step 2: Convert to grayscale
    gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
    # Step 3: CLAHE — adaptive contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4,4))
    eq = clahe.apply(gray)
    # Step 4: Unsharp masking — sharpen character strokes
    blur = cv2.GaussianBlur(eq, (0,0), 1.5)
    sharp = cv2.addWeighted(eq, 1.8, blur, -0.8, 0)
    # Step 5: Bilateral denoise — smooth noise while preserving edges
    denoised = cv2.bilateralFilter(sharp, d=5, sigmaColor=40, sigmaSpace=40)
    return cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)
```

### Stage 6 — PaddleOCR for Indian Licence Plates

PaddleOCR PP-OCRv3 achieves ~92–95% character accuracy on Indian licence plates versus ~55–70% for Tesseract v5. It is the only production-ready OCR engine that handles Indian LP fonts robustly on edge hardware via ONNX Runtime.

```python
from paddleocr import PaddleOCR
import re

ocr = PaddleOCR(
    use_angle_cls=True,
    lang='en',
    rec_model_dir='models/paddleocr_rec_indian',
    use_gpu=False,    # True on Jetson
    show_log=False,
)

VALID_LP = re.compile(r'^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$')
BH_LP    = re.compile(r'^[0-9]{2}BH[0-9]{4}[A-Z]{2}$')

def read_plate(plate_img):
    result = ocr.ocr(plate_img, cls=True)
    if not result or not result[0]:
        return '', 0.0
    text = ''.join([line[1][0] for line in result[0]])
    conf = float(np.mean([line[1][1] for line in result[0]]))
    cleaned = re.sub(r'[^A-Z0-9]', '', text.upper().replace(' ', ''))
    is_valid = bool(VALID_LP.match(cleaned) or BH_LP.match(cleaned))
    return cleaned, conf, is_valid
```

---

## 7. All Datasets — Complete Curated Master List

### Dataset Group A — Pedestrian & Vehicle Detection (Objectives 1, 2, 3)

| Dataset | Size | Relevant Classes | URL | Used In |
|---|---|---|---|---|
| **CrowdHuman** | 470k persons, 150k images | person, head | kaggle.com/datasets/kinguistics/crowdhuman | Obj 1 |
| **Caltech Pedestrian** | 350k+ bboxes | person | kaggle.com → borhanitrash/caltech-pedestrian-dataset | Obj 1 |
| **COCO 2017** | 120k images, 80 classes | person, vehicle, bicycle, motorcycle | cocodataset.org | Obj 1, 2, 3 |
| **UA-DETRAC** | 140k frames | car, bus, van, motorcycle | detrac.smiles.pub | Obj 1, 3 |
| **Indian Driving Dataset (IDD)** | 10,004 images | 26 Indian-specific classes including two-wheeler, auto | idd.insaan.iiit.ac.in | Obj 2, 3 — **Critical** |
| **BDD100K** | 100k frames | motorcycle, bicycle, car, person, traffic light | bdd-data.berkeley.edu | Obj 2, 3 |
| **DAWN** | 1,000 images | all vehicles in fog/rain/snow | kaggle.com/datasets/amlanpraharaj/dawn-dataset | All (adverse conditions) |

**Combined dataset build for Obj 1 detection:**

```
CrowdHuman + Caltech + COCO (person+vehicle subset):   ~27,000 images
Split: 70% train / 15% val / 15% test
Target: 15,000 labelled person images + 10,000 vehicle images minimum
```

### Dataset Group B — Age Estimation (Objective 1)

| Dataset | Size | Age Range | URL | Notes |
|---|---|---|---|---|
| **UTKFace** | 20,000+ faces | 0–116 years | kaggle.com/datasets/jangedoo/utkface-new | **Primary** — age encoded in filename |
| **IMDB-WIKI** | 500k+ faces | 0–100 years | data.vision.ee.ethz.ch/cvl/rrothe/imdb-wiki/ | Large — filter noisy samples |
| **AgeDB** | 16,516 faces | 1–101 years | ibug.doc.ic.ac.uk/resources/agedb/ | Clean, well-annotated |
| **AFAD** | 160k+ faces | 15–40 years | afad-dataset.github.io | Asian demographic supplement |

**Label mapping for training:**

```
Child:   age < 15   → Class 0 → VPI weight 2
Adult:   15 ≤ age < 60 → Class 1 → VPI weight 1
Elderly: age ≥ 60   → Class 2 → VPI weight 3

Training approach: Train as regression (predict raw age 0–100 via MAE loss),
then apply threshold rules in inference. More data-efficient than direct
3-class classification. SSR-Net natively supports this regression approach.
```

### Dataset Group C — Assistive Device Detection (Objective 1)

| Dataset | Size | Classes | URL | Notes |
|---|---|---|---|---|
| **Roboflow Wheelchair Detection** | ~3,000 images | wheelchair, person | universe.roboflow.com → search: wheelchair | Export in YOLOv8 format |
| **White Cane Detection** | ~800 images | cane, blind person | universe.roboflow.com → search: white cane | Supplement with manual annotation |
| **Assistive Mobility Devices** | ~2,000 images | wheelchair, crutches, walker | universe.roboflow.com → assistive devices | Multi-device combined |
| **OpenImages V7 — Wheelchair** | ~1,200 images | Wheelchair | storage.googleapis.com/openimages/ | Pull via fiftyone `classes=['Wheelchair']` |

**Combined target:** 5,000–8,000 annotated images across all 4 assistive device classes.

### Dataset Group D — Vulnerability Classifier — MobileNetV3 (Objective 1)

| Class | VPI Weight | Data Source | Target Images |
|---|---|---|---|
| child (0) | 2 | UTKFace age<15 crops + Caltech person crops + manual | 4,000+ |
| adult (1) | 1 | CrowdHuman adult crops | 6,000+ |
| elderly (2) | 3 | UTKFace age≥60 + IMDB-WIKI elderly subset | 4,000+ |
| wheelchair (3) | 5 | Roboflow wheelchair — crop person+device region | 3,000+ |
| blind_cane (4) | 4 | White cane Roboflow — crop person+cane region | 2,000+ |
| **TOTAL** | | | **~19,000 images** |

### Dataset Group E — Traffic Signal Classification (Objective 2)

| Dataset | Size | Classes | URL | Notes |
|---|---|---|---|---|
| **LISA Traffic Light Dataset** | ~7,800 images | red, green, yellow, off | kaggle.com/datasets/mbornoe/lisa-traffic-light-dataset | Primary baseline |
| **Bosch Small Traffic Lights** | ~13,000 images | red, green, yellow | hci.iwr.uni-heidelberg.de/node/6132 | Supplementary |
| **Self-collected Indian signals** | 500–1,000 images | red, green, yellow, unknown | Manual collection at local intersections | **Critical for domain adaptation** |

### Dataset Group F — Two-Wheeler Detection (Objective 3)

| Dataset | Size | Classes | URL | Notes |
|---|---|---|---|---|
| **COCO 2017 motorcycle/bicycle** | ~8,000 images | motorcycle, bicycle | cocodataset.org | Base pretrain |
| **IDD — two-wheeler class** | ~5,000 images | two-wheeler, auto | idd.insaan.iiit.ac.in | Indian-specific — critical |
| **UA-DETRAC motorcycle** | ~4,000 images | motorcycle | detrac.smiles.pub | Supplementary |
| **BDD100K motorcycle/bicycle** | ~6,000 images | motorcycle, bicycle | bdd-data.berkeley.edu | Diverse conditions |
| **Roboflow Indian two-wheeler** | ~3,000 images | motorcycle, scooter, bicycle | universe.roboflow.com → search: "two wheeler india" | Indian specific |
| **DAWN adverse conditions** | ~1,000 images | all vehicles in rain/fog | kaggle.com → amlanpraharaj/dawn-dataset | Weather robustness |
| **Self-collected deployment site** | 200+ images | all two-wheeler classes | Manual annotation at deployment camera | **Mandatory** |

### Dataset Group G — Licence Plate Localisation (Objective 3)

| Dataset | Size | Classes | URL | Notes |
|---|---|---|---|---|
| **Open Images V7 — Vehicle Registration Plate** | ~10,000 images | licence_plate | storage.googleapis.com/openimages/ | Pull via fiftyone |
| **CCPD-Base + CCPD-Blur + CCPD-Night** | ~140,000 images | licence_plate | kaggle.com/datasets/nicholasjhana/ccpd-2019-chinese-city-parking | Largest LP localisation set |
| **UFPR-ALPR** | ~4,500 images | licence_plate | web.inf.ufpr.br/vri/databases/ufpr-alpr/ | Also has OCR labels |
| **Roboflow Indian LP Detection** | ~5,000–10,000 images | licence_plate | universe.roboflow.com → "indian number plate detection" | Indian-specific — critical |
| **Self-collected deployment site** | 200+ images | licence_plate | Manual annotation | **Mandatory** |

### Dataset Group H — OCR Fine-Tuning for Indian LP (Objective 3)

| Dataset | Size | Format | URL | Notes |
|---|---|---|---|---|
| **UFPR-ALPR OCR labels** | ~4,500 plates | image + text label | web.inf.ufpr.br/vri/databases/ufpr-alpr/ | Same as Group G |
| **Indian LP Kaggle** | ~8,000 plate crops | image + CSV with plate text | kaggle.com → saisirishan/indian-vehicle-dataset | Indian fonts |
| **Synthetic Indian plates** | 10,000 generated | Python-rendered | Generated locally (script in Obj 3 guide) | Use for augmentation |
| **Self-collected annotated plates** | 200+ plates | image + text label | Manual annotation at site | **Mandatory** |

---

## 8. All Models — Edge Device Master Reference Table

> Every model listed here has been specifically chosen to run within the hardware constraints of Raspberry Pi 4 (4GB) and NVIDIA Jetson Nano (4GB). Any model not in this table is NOT used in this project.

### Objective 1 — Crossing Intelligence Models

| Model | Task | Architecture | Format | Size | Pi4 Latency | Jetson Latency | Source Weights |
|---|---|---|---|---|---|---|---|
| **pedestrian_int8.tflite** | Person + vehicle detection | YOLOv8n | TFLite INT8 | 3.2 MB | ~55ms @ 320px | ~15ms @ 640px | COCO pretrain → fine-tune |
| **face_detect.tflite** | Face detection | MTCNN (P+R+O-Net cascade) | TFLite | 1.8 MB | ~40ms / person | ~8ms / person | facenet-pytorch pretrain |
| **age_ssrnet.tflite** | Age regression | SSR-Net | TFLite INT8 | 0.9 MB | ~30ms / face | ~5ms / face | Train on UTKFace |
| **assistive_int8.tflite** | Wheelchair/cane/crutch | YOLOv8n | TFLite INT8 | 3.2 MB | ~55ms @ 320px | ~15ms @ 640px | COCO → Roboflow fine-tune |
| **classifier_int8.tflite** | 5-class vulnerability | MobileNetV3-Small | TFLite INT8 | 4.5 MB | ~25ms / person | ~10ms / person | ImageNet → fine-tune |
| **VPI Engine** | Score computation | Rule-based Python | Pure Python | 0 MB | <1ms | <1ms | No training |
| **Signal GPIO** | Relay trigger | Rule-based Python | Pure Python | 0 MB | <1ms | <1ms | No training |
| **TOTAL Obj 1** | | | | **13.6 MB** | **~90ms (5 persons)** | **~30ms (5 persons)** | |

### Objective 2 — Smart Mobility Stick Models

| Model | Task | Architecture | Format | Size | Pi4 Latency | Pi Zero 2W Latency | Source Weights |
|---|---|---|---|---|---|---|---|
| **stick_detect_int8.tflite** | Vehicle + obstacle detection | YOLOv8n (eye-level) | TFLite INT8 | 3.2 MB | ~55ms @ 320px | ~200ms @ 256px | COCO + IDD fine-tune |
| **signal_cls_int8.tflite** | Traffic signal state | MobileNetV3-Small | TFLite INT8 | 4.5 MB | ~25ms / crop | ~90ms / crop | LISA + Indian fine-tune |
| **Distance Engine** | Monocular TTC | Physics formula | Pure Python | 0 MB | <1ms | <1ms | No training |
| **Risk Engine** | Alert decision | Scoring formula | Pure Python | 0 MB | <1ms | <1ms | No training |
| **TOTAL Obj 2** | | | | **7.7 MB** | **~82ms** | **~293ms** | |

### Objective 3 — Footpath Enforcement Models

| Model | Task | Architecture | Format | Size | Pi4 Latency | Jetson Latency | Source Weights |
|---|---|---|---|---|---|---|---|
| **twowheeler_int8.tflite** | Two-wheeler detection | YOLOv8n (footpath angle) | TFLite INT8 | 3.2 MB | ~55ms @ 320px | ~22ms @ 640px | COCO + IDD + Roboflow |
| **lp_localise_int8.tflite** | Plate bounding box | YOLOv8n | TFLite INT8 | 3.2 MB | ~40ms | ~18ms | CCPD + UFPR + Indian LP |
| **ByteTrack** | Multi-object tracking | IoU matching | Pure Python | ~0.5 MB | ~5ms | ~3ms | No training (built-in) |
| **CLAHE Enhancement** | Plate image quality | Classical OpenCV | OpenCV | 0 MB | ~8ms | ~5ms | No training |
| **paddleocr_det.onnx** | Text region detection | DB (DifferentiableBinarization) | ONNX | 2.8 MB | ~45ms | ~18ms | Pre-trained (no fine-tune) |
| **paddleocr_rec_indian.onnx** | Character recognition | CRNN-based | ONNX | 8.0 MB | ~90ms | ~35ms | PP-OCRv3 → Indian fine-tune |
| **paddleocr_cls.onnx** | Angle correction | MobileNetV1-based | ONNX | 1.0 MB | ~15ms | ~6ms | Pre-trained (no fine-tune) |
| **TOTAL Obj 3** | | | | **18.7 MB** | **~258ms (violation trigger only)** | **~107ms** | |

### Grand Total Across All Three Objectives

```
Total model storage (all formats on device):    ~40 MB
Total RAM at runtime (Pi 4, all objectives):    ~1.2 GB
Objectives run as independent processes:         each on separate core
Shared models (YOLOv8n base):                   1 base binary shared
Cloud calls required:                           Zero
Internet required for inference:                Zero
```

---

## 9. Environment Setup — Training Machine

```bash
# Training machine requirements:
# NVIDIA GPU with ≥8 GB VRAM (RTX 3060 or better)
# CUDA 11.8 + cuDNN 8.6
# Python 3.10, Conda package manager
# Storage: ≥50 GB for datasets + checkpoints

conda create -n iot_pedestrian python=3.10 -y
conda activate iot_pedestrian

# Core ML frameworks
pip install ultralytics \
    torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cu118

pip install tensorflow==2.12.0 \
    tensorflow-addons \
    keras

# Computer vision and augmentation
pip install opencv-python-headless \
    albumentations \
    pillow \
    scikit-image

# Dataset management
pip install roboflow \
    fiftyone \
    kaggle \
    pandas \
    numpy

# Face detection
pip install facenet-pytorch \
    insightface \
    onnxruntime-gpu

# OCR
pip install paddlepaddle-gpu \
    paddleocr \
    paddle2onnx

# Model conversion
pip install onnx \
    onnxruntime-gpu \
    onnx-tf \
    tf2onnx

# Edge deployment tools
pip install paho-mqtt \
    fastapi \
    uvicorn

# Verify GPU
python -c "import torch; print('GPU:', torch.cuda.get_device_name(0))"
python -c "from ultralytics import YOLO; m=YOLO('yolov8n.pt'); print('YOLO OK')"
```

**Edge device (Raspberry Pi 4) runtime dependencies only:**

```bash
# On Raspberry Pi 4 — runtime ONLY, no training
pip install tflite-runtime \
    opencv-python-headless \
    numpy \
    paddleocr \
    onnxruntime \   # NOT onnxruntime-gpu
    paho-mqtt \
    RPi.GPIO \
    smbus2        # for I2C IMU sensor
```

---

## 10. Edge Conversion — Complete Pipeline

### YOLOv8n → TFLite INT8 (All Objectives)

```python
from ultralytics import YOLO

# Objective 1 — pedestrian detector
model = YOLO("runs/obj1/pedestrian_v1/weights/best.pt")
model.export(
    format="tflite",
    int8=True,
    data="datasets/pedestrian_vehicles/data.yaml",
    imgsz=320,        # 320 for Pi 4; 640 for Jetson
    simplify=True,
    nms=True,         # bake NMS into TFLite graph
)
# Produces: best_int8.tflite (~3.2 MB)

# Objective 3 — two-wheeler detector (same process, different weights)
model = YOLO("runs/obj3/twowheeler_v1/weights/best.pt")
model.export(format="tflite", int8=True,
             data="datasets/merged_twowheeler/data.yaml", imgsz=320)
```

### MobileNetV3 PyTorch → ONNX → TFLite INT8

```python
import torch, onnx, tensorflow as tf

# Step 1: Export to ONNX
dummy = torch.randn(1, 3, 224, 224)
torch.onnx.export(model, dummy, 'classifier.onnx',
    opset_version=12,
    input_names=['input'], output_names=['output'],
    dynamic_axes={'input': {0: 'batch'}})

# Step 2: ONNX → TensorFlow SavedModel
import onnx_tf
onnx_model = onnx.load('classifier.onnx')
tf_rep = onnx_tf.backend.prepare(onnx_model)
tf_rep.export_graph('classifier_tf_saved')

# Step 3: TF SavedModel → TFLite INT8
converter = tf.lite.TFLiteConverter.from_saved_model('classifier_tf_saved')
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type  = tf.int8
converter.inference_output_type = tf.int8
tflite_model = converter.convert()
open('models/classifier_int8.tflite', 'wb').write(tflite_model)
```

### PaddleOCR → ONNX (for ONNX Runtime on Pi/Jetson)

```bash
# Fine-tune PaddleOCR recognition on Indian LP data first (60 epochs)
python tools/train.py \
    -c configs/rec/PP-OCRv3/en_PP-OCRv3_rec.yml \
    -o Global.pretrained_model=en_PP-OCRv3_rec_train/best_accuracy \
       Global.epoch_num=60 \
       Train.dataset.label_file_list=["datasets/ocr_combined/train_labels.txt"]

# Export to ONNX
paddle2onnx \
    --model_dir output/paddleocr_indian_rec/ \
    --model_filename inference.pdmodel \
    --params_filename inference.pdiparams \
    --save_file models/paddleocr_rec_indian.onnx \
    --opset_version 11
```

### Jetson Nano — TensorRT Conversion (Optional, 3–5× Speedup)

```python
# Run ON Jetson Nano device, not training machine
from ultralytics import YOLO

model = YOLO("models/pedestrian_v1.pt")
model.export(
    format="engine",
    device=0,
    half=True,          # FP16 on Maxwell GPU
    simplify=True,
    workspace=2,        # GB VRAM for TensorRT workspace
)
# Produces: best.engine
# Load as: model = YOLO('best.engine')
# Speed: ~40 FPS vs ~18 FPS for TFLite INT8 on Jetson
```

### Quantisation Accuracy Validation (Mandatory Step)

```bash
# ALWAYS validate INT8 model accuracy before deploying
# INT8 should drop mAP50 by no more than 3% vs FP32

yolo detect val \
    model=models/pedestrian_int8.tflite \
    data=datasets/pedestrian_vehicles/data.yaml \
    split=test \
    device=cpu

# If drop > 5%: use more calibration images during export
# If drop > 10%: switch to FP16 quantisation instead of INT8
```

---

## 11. Evaluation & Acceptance Criteria — All Objectives

### Objective 1 Acceptance Criteria

| Model | Metric | Minimum | Production Target |
|---|---|---|---|
| YOLOv8n Pedestrian Detection | mAP50 (person) | > 0.75 | > 0.85 |
| YOLOv8n Pedestrian Detection | False Negative Rate | < 15% | < 8% |
| MTCNN Face Detection | Face Detection Recall | > 0.85 | > 0.92 |
| SSR-Net Age Estimation | MAE (years) | < 7 | < 5 |
| Age Classification (3-class) | Macro F1 | > 0.78 | > 0.88 |
| MobileNetV3 Vulnerability Classifier | Weighted F1 (5-class) | > 0.80 | > 0.88 |
| Assistive Device Detector | mAP50 (wheelchair) | > 0.68 | > 0.78 |
| Assistive Device Detector | mAP50 (white cane) | > 0.60 | > 0.72 |
| Full Pipeline (Pi 4) | End-to-end latency | < 200ms | < 120ms |
| Full Pipeline (Jetson Nano) | End-to-end latency | < 100ms | < 60ms |
| VPI Engine | Correctness on labelled test set | 100% | 100% |

### Objective 2 Acceptance Criteria

| Model | Metric | Minimum | Production Target |
|---|---|---|---|
| YOLOv8n Vehicle Detection (stick) | mAP50 (car) | > 0.78 | > 0.88 |
| YOLOv8n Vehicle Detection (stick) | mAP50 (motorcycle) | > 0.75 | > 0.85 |
| Distance Estimation | Accuracy ±25% at 1–15m | > 80% | > 90% |
| TTC Computation | False DANGER rate | < 5% | < 2% |
| Traffic Signal Classifier | Accuracy (4 classes) | > 88% | > 94% |
| Traffic Signal — Indian | Accuracy on Indian signals | > 80% | > 90% |
| Full Pipeline (Pi 4) | Latency | < 200ms | < 100ms |
| Full Pipeline (Pi Zero 2W) | Latency | < 500ms | < 300ms |

### Objective 3 Acceptance Criteria

| Model | Metric | Minimum | Production Target |
|---|---|---|---|
| YOLOv8n Two-Wheeler Detection | mAP50 (motorcycle) | > 0.80 | > 0.88 |
| YOLOv8n Two-Wheeler Detection | mAP50 (scooter) | > 0.75 | > 0.83 |
| LP Localiser | mAP50 (licence_plate) | > 0.85 | > 0.92 |
| LP Localiser | Recall @ conf=0.3 | > 0.90 | > 0.95 |
| PaddleOCR (Indian fine-tuned) | Character accuracy | > 90% | > 95% |
| PaddleOCR (Indian fine-tuned) | Word accuracy (full plate) | > 80% | > 92% |
| Full e-Challan Pipeline | Precision (valid challans) | > 88% | > 95% |
| Full e-Challan Pipeline | Recall (caught violations) | > 75% | > 85% |
| Full Pipeline (Pi 4) | Violation latency | < 300ms | < 200ms |
| Full Pipeline (Jetson) | Violation latency | < 120ms | < 80ms |

### Common Failure Modes & Fixes — All Objectives

| Failure | Objective | Symptom | Fix |
|---|---|---|---|
| Person detected as vehicle | Obj 1 | High FP rate from poles/signs | Hard negative mining — add 500+ non-person frames |
| Child in stroller misclassified | Obj 1 | Adult classification for stroller scenes | Add stroller images with child label in body classifier training |
| Face not detected at distance > 10m | Obj 1 | Age always defaulting to body path | Reduce MTCNN min_face_size to 15px; lower confidence threshold |
| Night accuracy drops > 15% | All | Low mAP at night | Add night-time images to all datasets; add IR illumination |
| Vehicle distance estimate inaccurate | Obj 2 | TTC triggers too early or too late | Recalibrate focal length; add vehicle-class-specific width constants |
| Signal not detected at angle | Obj 2 | Signal classifier not triggered | Lower YOLOv8n confidence for traffic_signal class to 0.25 |
| Two-wheeler not detected at elevation | Obj 3 | FNR > 20% from footpath camera | Add top-down view images from IDD dataset during training |
| Plate blurry from motion | Obj 3 | OCR confidence < 0.5 | Switch to global shutter camera; add motion blur augmentation |
| Duplicate challans same vehicle | Obj 3 | Multiple challans per crossing | Tune ByteTrack cooldown timer to 60–120 seconds |
| Invalid plate format from OCR | Obj 3 | Low validation pass rate | Fine-tune PaddleOCR on more Indian LP data |

---

## 12. Production Deployment Architecture

### File Structure on Raspberry Pi / Jetson Nano

```
/home/pi/pedestrian_ai/
│
├── obj1_main.py              # Objective 1 inference loop
├── obj2_main.py              # Objective 2 inference loop
├── obj3_main.py              # Objective 3 inference loop
│
├── shared/
│   ├── vpi_engine.py         # VPI computation (shared)
│   ├── signal_controller.py  # GPIO relay interface (Obj 1)
│   ├── alert_system.py       # Haptic + audio alerts (Obj 2)
│   └── utils.py              # Common utility functions
│
├── models/
│   ├── pedestrian_int8.tflite      # Obj 1 — person + vehicle
│   ├── face_detect.tflite          # Obj 1 — MTCNN
│   ├── age_ssrnet.tflite           # Obj 1 — SSR-Net
│   ├── classifier_int8.tflite      # Obj 1 — MobileNetV3 (vulnerability)
│   ├── assistive_int8.tflite       # Obj 1 — wheelchair/cane
│   ├── stick_detect_int8.tflite    # Obj 2 — vehicle + obstacle
│   ├── signal_cls_int8.tflite      # Obj 2 — traffic signal
│   ├── twowheeler_int8.tflite      # Obj 3 — two-wheeler
│   ├── lp_localise_int8.tflite     # Obj 3 — plate localiser
│   ├── paddleocr_det/              # Obj 3 — OCR detector
│   ├── paddleocr_rec_indian/       # Obj 3 — OCR recogniser (fine-tuned)
│   └── paddleocr_cls/              # Obj 3 — OCR angle classifier
│
├── config/
│   ├── camera_calibration.json     # Focal length, FPS, resolution
│   ├── vpi_thresholds.json         # VPI score → extension mapping
│   ├── footpath_roi.json           # Footpath polygon (Obj 3)
│   ├── speed_calibration.json      # Pixels-per-metre ratio (Obj 3)
│   └── dashboard.json              # MQTT broker, API endpoint
│
├── logs/
│   ├── violations/                 # e-Challan evidence (Obj 3)
│   ├── vpi_events/                 # VPI extension log (Obj 1)
│   └── system.log                  # Errors, restarts, warnings
│
└── requirements_edge.txt           # tflite-runtime, opencv, paddleocr...
```

### Systemd Auto-Start Service

```ini
# /etc/systemd/system/pedestrian_ai.service

[Unit]
Description=Pedestrian AI Safety System
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/pedestrian_ai/obj1_main.py
WorkingDirectory=/home/pi/pedestrian_ai
Restart=always
RestartSec=5
User=pi

[Install]
WantedBy=multi-user.target

# Enable:  sudo systemctl enable pedestrian_ai
# Start:   sudo systemctl start pedestrian_ai
# Status:  sudo systemctl status pedestrian_ai
# Logs:    journalctl -u pedestrian_ai -f
```

### Final Hardware-Software Stack — All Objectives

| Layer | Component | Role | Latency/Notes |
|---|---|---|---|
| Capture | 1080p IP Camera (RTSP) | Frame acquisition | 25 FPS, H.264 |
| Edge Compute | Raspberry Pi 4 (4GB) or Jetson Nano | Full pipeline | TFLite INT8 or TensorRT |
| Detection | YOLOv8n INT8 TFLite | Person, vehicle, device, two-wheeler | ~55ms @ 320px (Pi4) |
| Classification | MobileNetV3-Small INT8 | Vulnerability / Signal state | ~25ms / crop |
| Age Estimation | SSR-Net INT8 TFLite | Child / adult / elderly | ~30ms / face |
| Tracking | ByteTrack (built-in YOLO) | Multi-object tracking | ~5ms / frame |
| VPI Engine | Python rule engine | VPI score → signal extension | < 1ms |
| Signal Control | GPIO → relay → VAC controller | Extend green timer | +10/+20/+30s |
| Plate OCR | PaddleOCR (ONNX Runtime) | Licence plate reading | ~90ms / plate (Pi4) |
| Wearable | ESP32 + BLE | Receive alert → haptic/audio | BLE broadcast from Pi |
| Dashboard | MQTT (background thread) | Push violations to police | Non-blocking |
| Logging | Local JSON files | Violation evidence + VPI events | 0 cloud dependency |

---

## 13. Development Timeline — All Three Objectives

| Phase | Week | Task | Deliverable | Pass Condition |
|---|---|---|---|---|
| **Data** | Week 1 | Download COCO, CrowdHuman, IDD, BDD100K; convert to YOLO format | `datasets/` directory complete | `yolo data check` passes without errors |
| **Data** | Week 1–2 | Download UTKFace, Roboflow assistive devices, CCPD, Indian LP sets | All datasets formatted | Visual sample check passes |
| **Data** | Week 2 | Collect 500 Indian street images manually, annotate via Roboflow Annotate | `datasets/self_collected/` | 500 images with YOLO labels |
| **Data** | Week 2 | Generate 10,000 synthetic Indian LP images | `datasets/synthetic_plates/` | 10k images + labels.txt |
| **Train** | Week 3 | Train YOLOv8n pedestrian+vehicle detector (Obj 1) — 100 epochs | `pedestrian_v1.pt` | mAP50 > 0.75 (person) |
| **Train** | Week 3–4 | Train YOLOv8n assistive device fine-tune (Obj 1) — 150 epochs | `assistive_v1.pt` | mAP50 > 0.68 (wheelchair) |
| **Train** | Week 4 | Train SSR-Net age estimator on UTKFace — 80 epochs | `age_ssrnet.h5` | MAE < 7 years on val |
| **Train** | Week 4–5 | Train MobileNetV3 5-class vulnerability classifier — 40 epochs | `classifier_v1.pt` | Weighted F1 > 0.80 |
| **Train** | Week 5 | Train MobileNetV3 traffic signal classifier (Obj 2) — 30 epochs | `signal_cls_v1.pt` | Accuracy > 88% |
| **Train** | Week 5–6 | Train YOLOv8n two-wheeler detector (Obj 3) — 120 epochs | `twowheeler_v1.pt` | mAP50 > 0.80 (motorcycle) |
| **Train** | Week 6 | Train YOLOv8n LP localiser (Obj 3) — 200 epochs | `lp_localise_v1.pt` | mAP50 > 0.85 (plate) |
| **Train** | Week 6–7 | Fine-tune PaddleOCR on Indian LP data — 60 epochs | `paddleocr_indian_rec/` | Word accuracy > 80% |
| **Convert** | Week 7 | Convert all models to TFLite INT8 / ONNX | All `models/*.tflite`, `*.onnx` | Total size < 50 MB |
| **Convert** | Week 7–8 | Benchmark all models on actual Pi 4 and Jetson Nano | Latency report | Pi4 pipeline < 200ms |
| **Integrate** | Week 8 | Build `obj1_main.py`, `obj2_main.py`, `obj3_main.py` inference loops | Three running main scripts | 30-minute crash-free run on device |
| **Test** | Week 9 | Run full evaluation protocol: unit test each model independently | Per-model evaluation reports | All models meet minimum thresholds |
| **Test** | Week 9 | Integration test: full pipeline on recorded test video | Integration test results | Precision > 88%, Recall > 75% (Obj 3) |
| **Test** | Week 9–10 | Edge-case and night-time testing; fix failure modes | Night test results | < 10% accuracy drop vs day |
| **Deploy** | Week 10 | On-site installation: cameras, ROI calibration, GPIO wiring | All three systems live | Test event confirmed on each system |
| **Monitor** | Week 10+ | Daily review of first 200 challans; VPI event logs | Manual review log | False positive rate < 5% |

---

## 14. Critical Success Factors & Final Specifications

### Top 5 Rules That Govern Every Decision in This Project

**Rule 1 — Edge Constraint Is Absolute**
Every model choice, every dataset decision, every latency target derives from the Pi 4 / Jetson Nano hardware constraint. A model that achieves 99% accuracy but requires 500ms on Pi 4 is categorically unusable. Architecture decides first; accuracy optimises second.

**Rule 2 — Local Indian Data Beats Global Dataset Volume**
600 well-annotated images from the actual deployment location in Bangalore traffic will outperform 6,000 generic COCO images for detecting Indian scooters in Indian lighting conditions. Prioritise self-collection. The IDD (Indian Driving Dataset) is the single most valuable external dataset in this project.

**Rule 3 — mAP and Latency Must Always Be Measured Together**
A model with mAP50=0.90 that takes 180ms per inference is useless in this pipeline. Every model evaluation report must include both accuracy metrics AND measured latency on the actual target device. Never evaluate latency only on a training GPU.

**Rule 4 — Transfer Learning Always — Never Train from Scratch**
No model in this project is trained from random initialisation. YOLOv8n always starts from COCO-pretrained weights. MobileNetV3 always starts from ImageNet weights. PaddleOCR always starts from PP-OCRv3 weights. Training from scratch on project-scale data budgets produces inferior models to fine-tuned pretrained models.

**Rule 5 — The VPI Engine Is the System's Core Value**
The VPI computation (Stage 6, Objective 1) is the entire reason this system exists. Even with mediocre model accuracy (say, F1=0.75 on the classifier), if the VPI thresholds are correctly calibrated through ablation testing, the system still produces meaningful signal extensions. Spend time on threshold tuning — run at least 50 labelled test scenarios through the VPI engine and verify the output is correct.

### Final System Specifications at Deployment

| Parameter | Specification |
|---|---|
| Total model storage — all three objectives | ~40 MB |
| RAM usage at runtime — Pi 4 (Obj 1 only) | ~380 MB |
| RAM usage at runtime — Pi 4 (all three) | ~900 MB (run as separate processes) |
| Processing frame rate — Pi 4, Obj 1 | ~12 FPS at full pipeline |
| Processing frame rate — Jetson Nano, Obj 1 | ~25 FPS at full pipeline |
| End-to-end latency — Jetson, Obj 1 typical | ~55ms |
| VPI classes supported | 5 (child, adult, elderly, blind, wheelchair) |
| Maximum signal extension, Obj 1 | +30 seconds above base timer |
| Minimum dataset size for acceptable accuracy | ~44,000 labelled images total across all objectives |
| Cloud dependency | **Zero — fully offline edge inference** |
| Network required for real-time inference | **None** |
| Network used for | Dashboard push (MQTT, background, optional) |
| Deployment enclosure rating | IP65 minimum (outdoor intersection) |
| Operating temperature | 0°C to 50°C (standard Pi 4 spec) |
| Auto-recovery on crash | systemd Restart=always, 5s recovery |

---

*IoT ML Development Guide — AI-Powered Predictive Crossing Assistant for Vulnerable Pedestrians*

*Edge AI · YOLOv8n · MobileNetV3-Small · SSR-Net · MTCNN · ByteTrack · PaddleOCR PP-OCRv3 · TFLite INT8 · TensorRT FP16 · VPI Engine*

*Raspberry Pi 4 / NVIDIA Jetson Nano · Zero Cloud · Sub-100ms Latency · Fully Offline*
