import { useState } from 'react'
import { AppShell } from '@/app/layout/AppShell'
import { ViolationFilters } from '@/modules/violations/components/ViolationFilters'
import { ViolationsTable } from '@/modules/violations/components/ViolationsTable'
import { ViolationFilterInput, useViolationsQuery } from '@/modules/violations/hooks/useViolationsQuery'
import { DataState } from '@/shared/components/DataState'

export function ViolationsPage() {
  const [filters, setFilters] = useState<ViolationFilterInput>({ limit: 25 })
  const query = useViolationsQuery(filters)

  return (
    <AppShell>
      <section className="section-card">
        <div className="section-header">
          <span className="section-icon">🚨</span>
          <h2 style={{ marginBottom: 0 }}>Violation Records</h2>
          <span className="badge badge-neutral" style={{ marginLeft: 'auto' }}>
            {query.data?.items.length ?? 0} results
          </span>
        </div>

        <ViolationFilters value={filters} onChange={setFilters} />

        <DataState
          isLoading={query.isLoading}
          error={query.error}
          isEmpty={(query.data?.items.length ?? 0) === 0}
          emptyMessage="No violations match current filters."
        >
          <ViolationsTable items={query.data?.items ?? []} />
        </DataState>
      </section>
    </AppShell>
  )
}
