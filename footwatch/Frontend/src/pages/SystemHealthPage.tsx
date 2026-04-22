import { AppShell } from '@/app/layout/AppShell'
import { AlertTicker } from '@/modules/alerts/components/AlertTicker'
import { useAlertFeedQuery } from '@/modules/alerts/hooks/useAlertFeedQuery'
import { useLiveCamerasQuery } from '@/modules/live-cameras/hooks/useLiveCamerasQuery'
import { Badge } from '@/shared/components/Badge'
import { DataState } from '@/shared/components/DataState'

export function SystemHealthPage() {
  const query = useLiveCamerasQuery()
  const alertsQuery = useAlertFeedQuery()

  const onlineCount = (query.data?.items ?? []).filter((c) => c.status === 'online').length
  const totalCount = query.data?.items.length ?? 0

  return (
    <AppShell>
      <section className="section-card">
        <div className="section-header">
          <span className="section-icon">💻</span>
          <h2 style={{ marginBottom: 0 }}>System Health</h2>
          <Badge tone={onlineCount === totalCount && totalCount > 0 ? 'success' : 'warning'}>
            {onlineCount}/{totalCount} online
          </Badge>
        </div>

        <DataState
          isLoading={query.isLoading}
          error={query.error}
          isEmpty={(query.data?.items.length ?? 0) === 0}
          emptyMessage="No health telemetry available."
        >
          <ul className="health-list">
            {(query.data?.items ?? []).map((item) => (
              <li className="health-item" key={item.camera_id}>
                <div className="row" style={{ gap: '0.5rem' }}>
                  <span className={`status-dot ${item.status === 'online' ? 'status-dot-online' : 'status-dot-offline'}`} />
                  <strong>{item.camera_id}</strong>
                </div>
                <Badge tone={item.status === 'online' ? 'success' : 'danger'}>{item.status}</Badge>
                <span className="font-mono text-sm">{item.latency_ms ? `${item.latency_ms} ms` : 'N/A'}</span>
              </li>
            ))}
          </ul>
        </DataState>
      </section>

      <section className="section-card">
        <div className="section-header">
          <span className="section-icon">🔔</span>
          <h2 style={{ marginBottom: 0 }}>Active Alerts</h2>
        </div>
        <DataState
          isLoading={alertsQuery.isLoading}
          error={alertsQuery.error}
          isEmpty={(alertsQuery.data?.length ?? 0) === 0}
          emptyMessage="No active alerts."
        >
          <AlertTicker alerts={alertsQuery.data ?? []} />
        </DataState>
      </section>
    </AppShell>
  )
}
