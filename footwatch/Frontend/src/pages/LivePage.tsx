import { AppShell } from '@/app/layout/AppShell'
import { CameraHealthGrid } from '@/modules/live-cameras/components/CameraHealthGrid'
import { useLiveCamerasQuery } from '@/modules/live-cameras/hooks/useLiveCamerasQuery'
import { DataState } from '@/shared/components/DataState'

export function LivePage() {
  const query = useLiveCamerasQuery()

  return (
    <AppShell>
      <section className="section-card">
        <div className="section-header">
          <span className="section-icon">📹</span>
          <h2 style={{ marginBottom: 0 }}>Live Camera States</h2>
          <span className="badge badge-accent" style={{ marginLeft: 'auto' }}>
            {query.data?.items.length ?? 0} cameras
          </span>
        </div>
        <DataState
          isLoading={query.isLoading}
          error={query.error}
          isEmpty={(query.data?.items.length ?? 0) === 0}
          emptyMessage="No live camera payloads available."
        >
          <CameraHealthGrid cameras={query.data?.items ?? []} />
        </DataState>
      </section>
    </AppShell>
  )
}
