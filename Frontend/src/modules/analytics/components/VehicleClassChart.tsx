import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from 'recharts'

type VehicleClassChartProps = {
  byClass: Record<string, number>
}

export function VehicleClassChart({ byClass }: VehicleClassChartProps) {
  const data = Object.entries(byClass).map(([name, value]) => ({ name, value }))

  return (
    <section className="section-card" id="vehicle-class-chart">
      <div className="section-header">
        <span className="section-icon">🏍️</span>
        <h3>Vehicle Class Distribution</h3>
      </div>
      <div style={{ width: '100%', height: 240 }}>
        <ResponsiveContainer>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis dataKey="name" stroke="#556378" fontSize={11} />
            <YAxis allowDecimals={false} stroke="#556378" fontSize={11} />
            <Tooltip
              contentStyle={{
                background: '#141c2b',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '8px',
                color: '#e8edf5',
                fontSize: '0.82rem',
              }}
            />
            <Bar dataKey="value" fill="#3b82f6" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
