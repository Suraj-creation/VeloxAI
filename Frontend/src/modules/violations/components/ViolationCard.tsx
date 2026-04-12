import { Link } from 'react-router-dom'
import { Violation } from '@/modules/violations/types/violation'
import { mapViolationForTable } from '@/modules/violations/utils/mapViolationForTable'

type ViolationCardProps = {
  violation: Violation
}

export function ViolationCard({ violation }: ViolationCardProps) {
  const row = mapViolationForTable(violation)

  return (
    <article className="section-card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <strong>{row.plate}</strong>
        <span className="pill">{row.status}</span>
      </div>
      <p className="muted" style={{ marginTop: '0.5rem' }}>
        {row.time}
      </p>
      <p style={{ marginTop: '0.5rem' }}>Camera: {row.cameraId}</p>
      <p>Speed: {row.speed}</p>
      <Link style={{ display: 'inline-block', marginTop: '0.75rem' }} to={`/violations/${row.id}`}>
        Open details
      </Link>
    </article>
  )
}
