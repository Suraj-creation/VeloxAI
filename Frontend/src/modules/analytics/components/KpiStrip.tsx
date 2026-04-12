import { DashboardSummary } from '@/modules/analytics/types/analytics'

type KpiStripProps = {
  data: DashboardSummary | undefined
}

const kpiConfig = [
  { key: 'total_violations', label: 'Total Violations', icon: '🚨', format: (v: number) => String(v) },
  { key: 'unique_plates', label: 'Unique Plates', icon: '🔢', format: (v: number) => String(v) },
  { key: 'avg_speed_kmph', label: 'Avg Speed', icon: '⚡', format: (v: number) => `${v.toFixed(1)} km/h` },
  { key: 'avg_ocr_confidence', label: 'OCR Confidence', icon: '🎯', format: (v: number) => `${(v * 100).toFixed(0)}%` },
] as const

export function KpiStrip({ data }: KpiStripProps) {
  const safe = data ?? {
    total_violations: 0,
    unique_plates: 0,
    avg_speed_kmph: 0,
    avg_ocr_confidence: 0,
    by_class: {},
    by_hour: {},
  }

  return (
    <section className="kpi-grid" id="kpi-strip">
      {kpiConfig.map((kpi) => {
        const value = safe[kpi.key as keyof typeof safe] as number
        return (
          <article className="kpi-card" key={kpi.key}>
            <div className="kpi-icon">{kpi.icon}</div>
            <p className="kpi-label">{kpi.label}</p>
            <p className="kpi-value">{kpi.format(value)}</p>
          </article>
        )
      })}
    </section>
  )
}
