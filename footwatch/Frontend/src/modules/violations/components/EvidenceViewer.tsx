import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getEvidenceUrl } from '@/modules/violations/api/getEvidenceUrl'

type EvidenceViewerProps = {
  violationId: string
}

const evidenceTypes = [
  { key: 'vehicle_highlighted', label: 'Highlighted Vehicle' },
  { key: 'full_frame', label: 'Full Frame' },
  { key: 'plate_crop_raw', label: 'Plate (Raw)' },
  { key: 'plate_crop_enhanced', label: 'Plate (Enhanced)' },
  { key: 'thumbnail', label: 'Thumbnail' },
] as const

export function EvidenceViewer({ violationId }: EvidenceViewerProps) {
  const [activeType, setActiveType] = useState<string>('full_frame')

  const query = useQuery({
    queryKey: ['evidence-url', violationId, activeType],
    queryFn: () => getEvidenceUrl(violationId, activeType),
  })

  return (
    <section className="section-card" id="evidence-viewer">
      <div className="section-header">
        <span className="section-icon">Evidence</span>
        <h3>Evidence</h3>
      </div>

      <div className="evidence-tabs">
        {evidenceTypes.map((type) => (
          <button
            key={type.key}
            className={`evidence-tab ${activeType === type.key ? 'evidence-tab-active' : ''}`}
            onClick={() => setActiveType(type.key)}
          >
            {type.label}
          </button>
        ))}
      </div>

      {query.isLoading ? (
        <div className="state-card" style={{ padding: '2rem' }}>
          <div className="loading-shimmer" style={{ height: '200px' }} />
          <p className="muted" style={{ marginTop: '1rem' }}>Fetching secure evidence link...</p>
        </div>
      ) : query.error ? (
        <div className="state-card state-card-error">
          <p className="text-danger">Failed to load evidence URL</p>
          <p className="muted text-sm" style={{ marginTop: '0.5rem' }}>
            Evidence URLs are time-bound signed links. Try refreshing.
          </p>
        </div>
      ) : query.data ? (
        <div>
          <a
            href={query.data.url}
            rel="noreferrer"
            target="_blank"
            className="btn-primary"
            style={{ display: 'inline-block', marginBottom: '0.75rem' }}
          >
            Open Evidence
          </a>
          <p className="muted text-xs">
            Signed URL expires at: <code>{query.data.expires_at}</code>
          </p>
        </div>
      ) : null}
    </section>
  )
}
