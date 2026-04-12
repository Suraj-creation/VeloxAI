import { Link } from 'react-router-dom'
import { Badge } from '@/shared/components/Badge'
import { Violation } from '@/modules/violations/types/violation'
import { confidenceBadge } from '@/modules/violations/utils/confidenceBadge'
import { mapViolationForTable } from '@/modules/violations/utils/mapViolationForTable'

type ViolationsTableProps = {
  items: Violation[]
}

export function ViolationsTable({ items }: ViolationsTableProps) {
  return (
    <div className="table-wrapper" id="violations-table">
      <table className="data-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Plate</th>
            <th>Camera</th>
            <th>Class</th>
            <th>Speed</th>
            <th>Confidence</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const row = mapViolationForTable(item)
            const confidence = item.vehicle.plate_ocr_confidence

            return (
              <tr key={item.violation_id}>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{row.time}</td>
                <td>
                  <span className="pill">{row.plate}</span>
                </td>
                <td>{row.cameraId}</td>
                <td>
                  <Badge tone="info">{row.vehicleClass}</Badge>
                </td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>{row.speed}</td>
                <td>
                  <Badge tone={confidenceBadge(confidence)}>{row.confidence}</Badge>
                </td>
                <td>
                  <Badge tone={row.status === 'CONFIRMED_AUTO' ? 'success' : row.status === 'REQUIRES_REVIEW' ? 'warning' : 'neutral'}>
                    {row.status}
                  </Badge>
                </td>
                <td>
                  <Link to={`/violations/${item.violation_id}`} className="btn-ghost" style={{ padding: '4px 12px', fontSize: '0.78rem' }}>
                    View →
                  </Link>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
