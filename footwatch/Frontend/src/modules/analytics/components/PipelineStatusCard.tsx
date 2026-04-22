const stages = [
  { num: 1, name: 'Detection', model: 'YOLOv8n', latency: '~55ms', desc: 'Two-wheeler detection' },
  { num: 2, name: 'Enforcement', model: 'Rule-based', latency: '<1ms', desc: 'Full-frame pass' },
  { num: 3, name: 'Tracking', model: 'ByteTrack', latency: '~5ms', desc: 'Speed estimation' },
  { num: 4, name: 'Plate Detect', model: 'YOLOv8n-LP', latency: '~40ms', desc: 'LP localisation' },
  { num: 5, name: 'Enhancement', model: 'CLAHE+USM', latency: '~8ms', desc: 'Plate upscale' },
  { num: 6, name: 'OCR', model: 'PaddleOCR', latency: '~90ms', desc: 'Char recognition' },
  { num: 7, name: 'Evidence', model: 'Rule-based', latency: '~15ms', desc: 'Challan package' },
]

export function PipelineStatusCard() {
  return (
    <section className="section-card" id="pipeline-status">
      <div className="section-header">
        <span className="section-icon">⚙️</span>
        <h3>ML Pipeline — 7-Stage Edge Processing</h3>
        <span className="badge badge-accent" style={{ marginLeft: 'auto' }}>~214ms total</span>
      </div>

      <div className="pipeline-grid">
        {stages.map((stage) => (
          <div className="pipeline-stage" key={stage.num}>
            <div className="pipeline-stage-number">Stage {stage.num}</div>
            <div className="pipeline-stage-name">{stage.name}</div>
            <div className="pipeline-stage-model">{stage.model}</div>
            <div className="pipeline-stage-latency">{stage.latency}</div>
          </div>
        ))}
      </div>
    </section>
  )
}
