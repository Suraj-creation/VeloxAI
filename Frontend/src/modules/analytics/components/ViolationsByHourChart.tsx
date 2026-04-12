import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from 'recharts'

type ViolationsByHourChartProps = {
  byHour: Record<string, number>
}

export function ViolationsByHourChart({ byHour }: ViolationsByHourChartProps) {
  const data = Object.entries(byHour).map(([hour, count]) => ({ hour, count }))

  return (
    <section className="section-card" id="violations-by-hour-chart">
      <div className="section-header">
        <span className="section-icon">📈</span>
        <h3>Violations by Hour</h3>
      </div>
      <div style={{ width: '100%', height: 240 }}>
        <ResponsiveContainer>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis dataKey="hour" hide />
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
            <Line
              dataKey="count"
              stroke="#3b82f6"
              strokeWidth={2.2}
              type="monotone"
              dot={{ fill: '#3b82f6', r: 3 }}
              activeDot={{ r: 5, fill: '#60a5fa' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
