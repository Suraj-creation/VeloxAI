import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip, Legend } from 'recharts'

type OcrConfidenceChartProps = {
  confidenceValues: number[]
}

const COLORS = ['#22c55e', '#f59e0b', '#ef4444']

export function OcrConfidenceChart({ confidenceValues }: OcrConfidenceChartProps) {
  const buckets = {
    high: confidenceValues.filter((v) => v >= 0.8).length,
    medium: confidenceValues.filter((v) => v >= 0.65 && v < 0.8).length,
    low: confidenceValues.filter((v) => v < 0.65).length,
  }

  const data = [
    { name: 'High (≥80%)', value: buckets.high },
    { name: 'Medium (65-80%)', value: buckets.medium },
    { name: 'Low (<65%)', value: buckets.low },
  ]

  return (
    <section className="section-card" id="ocr-confidence-chart">
      <div className="section-header">
        <span className="section-icon">🎯</span>
        <h3>OCR Confidence</h3>
      </div>
      <div style={{ width: '100%', height: 240 }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              innerRadius={50}
              outerRadius={85}
              paddingAngle={3}
              strokeWidth={0}
            >
              {data.map((entry, index) => (
                <Cell key={`${entry.name}-${entry.value}`} fill={COLORS[index]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: '#141c2b',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '8px',
                color: '#e8edf5',
                fontSize: '0.82rem',
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: '0.75rem', color: '#8896ab' }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
