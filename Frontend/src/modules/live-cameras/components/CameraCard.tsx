import { Badge } from '@/shared/components/Badge'
import { formatDateTime, ageMs } from '@/shared/utils/date'
import { LiveCamera } from '@/modules/live-cameras/types/camera'

type CameraCardProps = {
  camera: LiveCamera
}

export function CameraCard({ camera }: CameraCardProps) {
  const isStale = ageMs(camera.last_seen_ts) > 30_000

  const tone =
    camera.status === 'online' && !isStale
      ? 'success'
      : camera.status === 'offline'
        ? 'danger'
        : 'warning'

  const statusLabel = isStale && camera.status === 'online' ? 'stale' : camera.status

  return (
    <article className="section-card" id={`camera-${camera.camera_id}`}>
      <div className="row-between">
        <div className="row" style={{ gap: '0.5rem' }}>
          <span className={`status-dot ${tone === 'success' ? 'status-dot-online' : tone === 'danger' ? 'status-dot-offline' : ''}`}
            style={tone === 'warning' ? { background: 'var(--color-warning)', boxShadow: '0 0 8px rgba(245,158,11,0.4)' } : {}}
          />
          <h3 style={{ fontSize: '0.9rem' }}>{camera.camera_id}</h3>
        </div>
        <Badge tone={tone}>{statusLabel}</Badge>
      </div>

      <p className="text-secondary text-sm" style={{ marginTop: '0.4rem' }}>
        {camera.location_name}
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginTop: '0.75rem' }}>
        <div>
          <span className="text-xs muted">FPS</span>
          <p className="text-primary" style={{ fontSize: '0.88rem', fontWeight: 600 }}>
            {camera.fps?.toFixed(1) ?? '—'}
          </p>
        </div>
        <div>
          <span className="text-xs muted">Latency</span>
          <p className="text-primary" style={{ fontSize: '0.88rem', fontWeight: 600 }}>
            {camera.latency_ms ? `${camera.latency_ms} ms` : '—'}
          </p>
        </div>
        <div>
          <span className="text-xs muted">Reconnects</span>
          <p className="text-primary" style={{ fontSize: '0.88rem', fontWeight: 600 }}>
            {camera.reconnects ?? 0}
          </p>
        </div>
        <div>
          <span className="text-xs muted">Last Seen</span>
          <p className="text-secondary" style={{ fontSize: '0.78rem' }}>
            {formatDateTime(camera.last_seen_ts)}
          </p>
        </div>
      </div>
    </article>
  )
}
