import { useEffect, useState } from 'react'

export function StatusBar() {
  const [clock, setClock] = useState(() => new Date().toLocaleTimeString())

  useEffect(() => {
    const id = window.setInterval(() => {
      setClock(new Date().toLocaleTimeString())
    }, 1_000)
    return () => window.clearInterval(id)
  }, [])

  return (
    <section className="status-bar" aria-live="polite">
      <div className="status-bar-item">
        <span className="status-dot status-dot-online" />
        <span>Pipeline Active</span>
      </div>
      <div className="status-bar-item">
        <span>Models: YOLOv8n (3.2MB) + LP-YOLO (3.2MB) + PaddleOCR (8MB)</span>
      </div>
      <div className="status-bar-item">
        <span>Polling: Live 3s · Violations 5s</span>
        <span style={{ marginLeft: '0.75rem', fontFamily: 'var(--font-mono)' }}>{clock}</span>
      </div>
    </section>
  )
}
