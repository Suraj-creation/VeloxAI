import { Link, useParams } from 'react-router-dom'
import { AppShell } from '@/app/layout/AppShell'
import { EvidenceViewer } from '@/modules/violations/components/EvidenceViewer'
import { ViolationDetailPanel } from '@/modules/violations/components/ViolationDetailPanel'
import { useViolationDetailsQuery } from '@/modules/violations/hooks/useViolationDetailsQuery'
import { DataState } from '@/shared/components/DataState'

export function ViolationDetailsPage() {
  const { id } = useParams()
  const query = useViolationDetailsQuery(id)

  return (
    <AppShell>
      <div className="row" style={{ marginBottom: '0.5rem' }}>
        <Link to="/violations" className="btn-ghost">← Back to Violations</Link>
      </div>

      <section className="section-card">
        <div className="section-header">
          <span className="section-icon">📋</span>
          <h2 style={{ marginBottom: 0 }}>Violation Details</h2>
          {query.data && (
            <span className="pill" style={{ marginLeft: 'auto' }}>{query.data.violation_id.slice(0, 8)}</span>
          )}
        </div>

        <DataState
          isLoading={query.isLoading}
          error={query.error}
          isEmpty={!query.data}
          emptyMessage="Violation record not found."
        >
          {query.data ? (
            <div className="detail-grid">
              <ViolationDetailPanel violation={query.data} />
              <EvidenceViewer violationId={query.data.violation_id} />
            </div>
          ) : null}
        </DataState>
      </section>
    </AppShell>
  )
}
