import { Violation } from '@/modules/violations/types/violation'
import { endpoints } from '@/shared/api/endpoints'
import { Badge } from '@/shared/components/Badge'
import { env } from '@/shared/config/env'
import { formatDateTime } from '@/shared/utils/date'

type ChallanPanelProps = {
  violation: Violation
}

const statusTone: Record<string, 'neutral' | 'success' | 'warning' | 'danger' | 'info'> = {
  READY: 'success',
  READY_FALLBACK: 'warning',
  PENDING_EVIDENCE: 'info',
  MANUAL_REVIEW_REQUIRED: 'danger',
  GENERATION_FAILED: 'danger',
}

export function ChallanPanel({ violation }: ChallanPanelProps) {
  const challan = violation.challan
  const status = challan?.status ?? 'PENDING_EVIDENCE'
  const semantic = challan?.semantic_record
  const downloadPath = challan?.download_path ?? endpoints.violationChallanDownload(violation.violation_id)
  const downloadHref = challan?.download_ready ? `${env.VITE_API_BASE_URL}${downloadPath}` : null

  return (
    <section className="section-card detail-grid-full" id="challan-panel">
      <div className="section-header">
        <span className="section-icon">Document</span>
        <h3>E-Challan</h3>
        <div style={{ marginLeft: 'auto' }}>
          <Badge tone={statusTone[status] ?? 'neutral'}>{status}</Badge>
        </div>
      </div>

      <div className="challan-grid">
        <div className="challan-card">
          <div className="detail-row">
            <span className="detail-label">Provider</span>
            <span className="detail-value">{challan?.provider ?? 'pending'}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Model</span>
            <span className="detail-value">{challan?.model ?? 'fallback'}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Fine Amount</span>
            <span className="detail-value">INR {challan?.fine_amount_inr ?? violation.fine_amount_inr}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Evidence Source</span>
            <span className="detail-value">{challan?.evidence_image_type ?? 'awaiting highlighted frame'}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Generated At</span>
            <span className="detail-value">
              {challan?.generated_at ? formatDateTime(challan.generated_at) : 'Not generated yet'}
            </span>
          </div>
        </div>

        <div className="challan-card">
          <div className="detail-row">
            <span className="detail-label">Violation Type</span>
            <span className="detail-value">{semantic?.violation_details.violation_type ?? 'FOOTPATH ENCROACHMENT'}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Severity</span>
            <span className="detail-value">{semantic?.violation_details.severity ?? 'moderate'}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Vehicle Description</span>
            <span className="detail-value">{semantic?.vehicle_details.vehicle_description ?? 'UNKNOWN'}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Vehicle Color</span>
            <span className="detail-value">{semantic?.vehicle_details.vehicle_color ?? 'UNKNOWN'}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Overall Confidence</span>
            <span className="detail-value">
              {typeof semantic?.confidence_scores.overall_confidence === 'number'
                ? semantic.confidence_scores.overall_confidence.toFixed(3)
                : 'N/A'}
            </span>
          </div>
        </div>
      </div>

      <div className="divider" />

      <div className="grid gap-sm">
        <div className="challan-actions">
          {downloadHref ? (
            <a className="btn-primary" href={downloadHref} rel="noreferrer" target="_blank">
              Download Challan PDF
            </a>
          ) : (
            <span className="badge badge-info">PDF will appear after the highlighted evidence frame is uploaded.</span>
          )}
          {challan?.manual_review_reason ? (
            <span className="badge badge-danger">Manual review: {challan.manual_review_reason}</span>
          ) : null}
          {challan?.generation_error ? (
            <span className="badge badge-warning">Gemini fallback used: {challan.generation_error}</span>
          ) : null}
        </div>

        <div className="challan-card">
          <span className="detail-label">Legal Summary</span>
          <p className="challan-copy">
            {semantic?.legal_summary ??
              'The backend will produce the legal challan summary once the highlighted vehicle frame and stable violation metadata are available.'}
          </p>
        </div>
      </div>
    </section>
  )
}
