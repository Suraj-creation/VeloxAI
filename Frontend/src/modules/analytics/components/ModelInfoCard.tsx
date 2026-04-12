const models = [
  {
    name: 'YOLOv8n — Two-Wheeler Detector',
    tag: 'Stage 1',
    details: [
      { label: 'Architecture', value: 'YOLOv8 Nano' },
      { label: 'Framework', value: 'TFLite INT8' },
      { label: 'Model Size', value: '3.2 MB' },
      { label: 'Input Size', value: '320×320 (Pi) / 640×640 (Jetson)' },
      { label: 'Classes', value: 'motorcycle, bicycle, e-scooter, scooter' },
      { label: 'Conf Threshold', value: '0.45' },
      { label: 'NMS IoU', value: '0.50' },
      { label: 'Source', value: 'Ultralytics HuggingFace' },
    ],
  },
  {
    name: 'YOLOv8n — Licence Plate Localiser',
    tag: 'Stage 4',
    details: [
      { label: 'Architecture', value: 'YOLOv8 Nano' },
      { label: 'Framework', value: 'TFLite INT8' },
      { label: 'Model Size', value: '3.2 MB' },
      { label: 'Input Size', value: '320×320 (cropped vehicle)' },
      { label: 'Classes', value: 'licence_plate' },
      { label: 'Conf Threshold', value: '0.30' },
      { label: 'Source', value: 'yasirfaizahmed/license-plate-detection' },
    ],
  },
  {
    name: 'PaddleOCR PP-OCRv3',
    tag: 'Stage 6',
    details: [
      { label: 'Architecture', value: 'PP-OCRv3 (text detect + recognize + cls)' },
      { label: 'Framework', value: 'ONNX Runtime' },
      { label: 'Model Size', value: '~8 MB' },
      { label: 'Language', value: 'English (Indian LP optimized)' },
      { label: 'Features', value: 'Angle classification, voting ensemble' },
      { label: 'LP Format', value: 'XX00XX0000 / 00BH0000XX' },
    ],
  },
]

export function ModelInfoCard() {
  return (
    <section className="section-card" id="model-info">
      <div className="section-header">
        <span className="section-icon">🤖</span>
        <h3>Model Registry — Pretrained (No Retraining)</h3>
      </div>

      <div className="model-info-grid">
        {models.map((model) => (
          <div className="model-card" key={model.name}>
            <div className="model-card-header">
              <h3 style={{ fontSize: '0.88rem' }}>{model.name}</h3>
              <span className="model-tag">{model.tag}</span>
            </div>
            <div className="grid gap-xs">
              {model.details.map((d) => (
                <div className="detail-row" key={d.label}>
                  <span className="detail-label">{d.label}</span>
                  <span className="detail-value text-sm">{d.value}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
