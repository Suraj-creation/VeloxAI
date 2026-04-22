import { AlertItem } from '@/modules/alerts/types/alert'
import { Badge } from '@/shared/components/Badge'

type AlertTickerProps = {
  alerts: AlertItem[]
}

export function AlertTicker({ alerts }: AlertTickerProps) {
  if (!alerts.length) {
    return null
  }

  return (
    <section className="section-card" aria-label="Live alerts">
      <h3>Alerts</h3>
      <ul style={{ listStyle: 'none', margin: '1rem 0 0', padding: 0, display: 'grid', gap: '0.75rem' }}>
        {alerts.map((alert) => (
          <li className="row" key={alert.id} style={{ justifyContent: 'space-between' }}>
            <span>{alert.message}</span>
            <Badge tone={alert.severity === 'critical' ? 'danger' : alert.severity === 'warning' ? 'warning' : 'info'}>
              {alert.severity}
            </Badge>
          </li>
        ))}
      </ul>
    </section>
  )
}
