# Challan Generation Architecture

## Goal

Build a reliable challan pipeline for footpath violations:

1. Edge device detects a confirmed violation.
2. Edge captures a highlighted evidence image for the tracked vehicle.
3. Backend stores the violation, waits for evidence if needed, and gates by OCR confidence.
4. Gemini enriches the record only after the violation is already confirmed by the edge pipeline.
5. Backend renders a PDF challan and exposes a download route.
6. Frontend shows challan status, legal summary, and a PDF download button.

## Responsibility Split

### Edge device

The Raspberry Pi remains the detection layer.

- `camera_node` publishes frames.
- `inference_node` detects vehicles.
- `tracking_node` keeps a stable track.
- `speed_estimation_node` computes speed.
- `violation_detection_node` confirms footpath encroachment.
- `mqtt_bridge_node` or the HTTP bridge sends only confirmed violations.

The edge must not ask Gemini to decide whether a violation happened. That decision stays with the vision pipeline.

### Backend

The backend is the semantic and legal layer.

- Normalizes and persists the violation.
- Waits for evidence if the highlighted frame is late.
- Sends image plus structured metadata to Gemini when confidence allows.
- Falls back to a restrained challan record if Gemini is unavailable.
- Generates a PDF artifact.
- Serves challan metadata and a download endpoint to the frontend.

### Frontend

The dashboard is the operator layer.

- Shows violation metadata.
- Shows evidence links.
- Shows challan status.
- Shows legal summary.
- Exposes the PDF download action.

## Edge Capture Plan

The edge side should generate challan evidence from the same stable track that triggered the violation.

### When to capture

Capture only when all of the following are true:

- footpath encroachment is confirmed
- the track is stable across several frames
- the vehicle box is large enough for readable evidence
- OCR confidence is available

### What to capture

Store and upload these assets per violation:

- `vehicle_highlighted`
  A cropped or tightly framed image of the violating vehicle with the target highlighted.
- `annotated_frame`
  Optional full scene image with boxes and labels.
- `full_frame`
  Raw source frame for audit.
- `plate_crop_raw`
  Plate crop before enhancement.
- `plate_crop_enhanced`
  Plate crop after enhancement.
- `thumbnail`
  Lightweight dashboard preview.

### Recommended edge sequence

1. Confirm violation on a stable track.
2. Freeze the best frame from that track.
3. Save `vehicle_highlighted` first.
4. Save full-frame and plate evidence.
5. Publish violation metadata immediately.
6. Publish `evidence-complete` once paths or object keys are ready.

This keeps the system responsive while still allowing the backend to wait for the final evidence image before generating the challan.

## Backend Flow

### Ingest

The backend accepts a violation payload with:

- `violation_id`
- `timestamp`
- `location`
- `vehicle`
- optional `evidence`

If evidence arrives later, the backend accepts a follow-up `evidence-complete` event and merges it into the stored violation.

### Confidence gate

- `plate_ocr_confidence < 0.65`
  mark `MANUAL_REVIEW_REQUIRED`
  do not auto-issue a PDF
- `plate_ocr_confidence >= 0.65`
  continue
- highlighted evidence missing
  mark `PENDING_EVIDENCE`
- highlighted evidence present
  continue to challan generation

### Gemini call

Gemini receives:

- highlighted vehicle image
- timestamp
- location name
- GPS
- camera id
- detected vehicle class
- estimated speed
- OCR plate text
- OCR confidence

Gemini returns only structured challan JSON. It does not create the PDF.

### Fallback behavior

If Gemini is unavailable or misformatted:

- keep the violation record alive
- generate a restrained fallback challan JSON
- create the PDF from fallback data
- mark the challan status as `READY_FALLBACK`

### PDF generation

The backend renders a downloadable PDF from stored challan JSON plus the selected evidence image.

Current implementation notes:

- PDF artifact path is stored on the violation record.
- Challan JSON is stored alongside the PDF.
- The query API exposes `GET /v1/violations/{violation_id}/challan-download`.

## Frontend Flow

The violation details page now shows:

- core violation metadata
- evidence tabs including `vehicle_highlighted`
- challan status
- semantic summary
- provider and model metadata
- PDF download button when ready

## State Model

The challan pipeline now uses these statuses:

- `PENDING_EVIDENCE`
- `MANUAL_REVIEW_REQUIRED`
- `READY`
- `READY_FALLBACK`
- `GENERATION_FAILED`

## Required Edge Contract

To fully connect `edge_ros2` with this backend, the edge payload should include:

```json
{
  "violation_id": "vio-123",
  "timestamp": "2026-04-23T14:23:07Z",
  "location": {
    "camera_id": "CAM-FOOTPATH-01",
    "location_name": "Whitefield Footpath Zone A",
    "gps_lat": 12.9698,
    "gps_lng": 77.7500
  },
  "vehicle": {
    "plate_number": "KA05AB1234",
    "plate_ocr_confidence": 0.91,
    "plate_format_valid": true,
    "vehicle_class": "motorcycle",
    "estimated_speed_kmph": 18.5,
    "track_id": 201
  },
  "evidence": {
    "vehicle_highlighted": "s3://.../vehicle_highlighted.jpg",
    "annotated_frame": "s3://.../annotated_frame.jpg",
    "full_frame": "s3://.../full_frame.jpg",
    "plate_crop_raw": "s3://.../plate_raw.jpg",
    "plate_crop_enhanced": "s3://.../plate_enhanced.jpg",
    "thumbnail": "s3://.../thumbnail.jpg"
  }
}
```

If the edge uploads evidence after the first violation event, it must call the evidence-complete endpoint with the same evidence object.

## Operational Checklist

- Edge sends stable-track violations only.
- Edge uploads `vehicle_highlighted` for challan generation.
- Backend waits for evidence instead of failing early.
- Low-confidence OCR is routed to manual review.
- Gemini enriches, but does not replace, edge detections.
- Frontend exposes the final PDF only when the backend says it is ready.
