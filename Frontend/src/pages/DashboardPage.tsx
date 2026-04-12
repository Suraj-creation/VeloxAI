import { AppShell } from '@/app/layout/AppShell'
import { CameraHealthGrid } from '@/modules/live-cameras/components/CameraHealthGrid'
import { useLiveCamerasQuery } from '@/modules/live-cameras/hooks/useLiveCamerasQuery'
import { KpiStrip } from '@/modules/analytics/components/KpiStrip'
import { OcrConfidenceChart } from '@/modules/analytics/components/OcrConfidenceChart'
import { VehicleClassChart } from '@/modules/analytics/components/VehicleClassChart'
import { ViolationsByHourChart } from '@/modules/analytics/components/ViolationsByHourChart'
import { PipelineStatusCard } from '@/modules/analytics/components/PipelineStatusCard'
import { ModelInfoCard } from '@/modules/analytics/components/ModelInfoCard'
import { useDashboardSummaryQuery } from '@/modules/analytics/hooks/useDashboardSummaryQuery'
import { ViolationsTable } from '@/modules/violations/components/ViolationsTable'
import { useViolationsQuery } from '@/modules/violations/hooks/useViolationsQuery'
import { DataState } from '@/shared/components/DataState'

export function DashboardPage() {
  const live = useLiveCamerasQuery()
  const violations = useViolationsQuery({ limit: 24 })
  const summary = useDashboardSummaryQuery()
  const confidenceValues = (violations.data?.items ?? [])
    .map((item) => item.vehicle.plate_ocr_confidence)
    .filter((value): value is number => typeof value === 'number')

  return (
    <AppShell>
      {/* KPI Summary Strip */}
      <KpiStrip data={summary.data} />

      {/* ML Pipeline Stages */}
      <PipelineStatusCard />

      {/* Live Camera Health */}
      <section className="section-card">
        <div className="section-header">
          <span className="section-icon">📹</span>
          <h2 style={{ marginBottom: 0 }}>Live Camera Health</h2>
        </div>
        <DataState
          isLoading={live.isLoading}
          error={live.error}
          isEmpty={(live.data?.items.length ?? 0) === 0}
          emptyMessage="No live cameras are reporting telemetry."
        >
          <CameraHealthGrid cameras={live.data?.items ?? []} />
        </DataState>
      </section>

      {/* Analytics Charts */}
      <section className="chart-grid">
        <VehicleClassChart byClass={summary.data?.by_class ?? {}} />
        <ViolationsByHourChart byHour={summary.data?.by_hour ?? {}} />
        <OcrConfidenceChart confidenceValues={confidenceValues} />
      </section>

      {/* Recent Violations */}
      <section className="section-card">
        <div className="section-header">
          <span className="section-icon">🚨</span>
          <h2 style={{ marginBottom: 0 }}>Recent Violations</h2>
          <span className="badge badge-neutral" style={{ marginLeft: 'auto' }}>
            {violations.data?.items.length ?? 0} records
          </span>
        </div>
        <DataState
          isLoading={violations.isLoading}
          error={violations.error}
          isEmpty={(violations.data?.items.length ?? 0) === 0}
          emptyMessage="No confirmed violations found in current window."
        >
          <ViolationsTable items={violations.data?.items ?? []} />
        </DataState>
      </section>

      {/* Model Registry */}
      <ModelInfoCard />
    </AppShell>
  )
}
