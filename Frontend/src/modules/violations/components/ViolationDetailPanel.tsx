import { Badge } from '@/shared/components/Badge'
import { formatDateTime } from '@/shared/utils/date'
import { formatPlate } from '@/shared/utils/plate'
import { formatSpeed } from '@/shared/utils/speed'
import { Violation } from '@/modules/violations/types/violation'

type ViolationDetailPanelProps = {
  violation: Violation
}

const fields = (v: Violation) => [
  { label: 'Violation ID', value: v.violation_id, mono: true },
  { label: 'Timestamp', value: formatDateTime(v.timestamp) },
  { label: 'Plate Number', value: formatPlate(v.vehicle.plate_number) },
  { label: 'Speed', value: formatSpeed(v.vehicle.estimated_speed_kmph) },
  { label: 'Vehicle Class', value: v.vehicle.vehicle_class ?? 'N/A' },
  { label: 'Track ID', value: v.vehicle.track_id ?? 'N/A' },
  { label: 'Camera', value: v.location.camera_id ?? 'N/A' },
  { label: 'Location', value: v.location.location_name ?? 'N/A' },
  { label: 'Fine Amount', value: `₹${v.fine_amount_inr}` },
  { label: 'Status', value: v.violation_status },
]

export function ViolationDetailPanel({ violation }: ViolationDetailPanelProps) {
  const confidence = violation.vehicle.plate_ocr_confidence
  const plateValid = violation.vehicle.plate_format_valid

  return (
    <section className="section-card" id="violation-detail-panel">
      <div className="section-header">
        <span className="section-icon">📋</span>
        <h3>Violation Metadata</h3>
      </div>

      <div className="grid gap-xs">
        {fields(violation).map((f) => (
          <div className="detail-row" key={f.label}>
            <span className="detail-label">{f.label}</span>
            <span className={`detail-value ${f.mono ? 'font-mono text-sm' : ''}`}>{String(f.value)}</span>
          </div>
        ))}

        <div className="detail-row">
          <span className="detail-label">OCR Confidence</span>
          <Badge tone={confidence != null && confidence >= 0.8 ? 'success' : confidence != null && confidence >= 0.65 ? 'warning' : 'danger'}>
            {typeof confidence === 'number' ? confidence.toFixed(3) : 'N/A'}
          </Badge>
        </div>

        <div className="detail-row">
          <span className="detail-label">Plate Format</span>
          <Badge tone={plateValid ? 'success' : 'danger'}>
            {plateValid ? '✓ Valid' : '✗ Invalid'}
          </Badge>
        </div>
      </div>

      <div className="divider" />

      <div className="section-header" style={{ marginBottom: '0.5rem' }}>
        <span className="section-icon">🤖</span>
        <h3 style={{ fontSize: '0.85rem' }}>ML Pipeline Info</h3>
      </div>
      <div className="grid gap-xs">
        <div className="detail-row">
          <span className="detail-label">Detection Model</span>
          <span className="model-tag">YOLOv8n</span>
        </div>
        <div className="detail-row">
          <span className="detail-label">LP Localiser</span>
          <span className="model-tag">YOLOv8n-LP</span>
        </div>
        <div className="detail-row">
          <span className="detail-label">OCR Engine</span>
          <span className="model-tag">PaddleOCR v3</span>
        </div>
        <div className="detail-row">
          <span className="detail-label">Tracker</span>
          <span className="model-tag">ByteTrack</span>
        </div>
      </div>
    </section>
  )
}
