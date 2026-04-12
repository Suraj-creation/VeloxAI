import { useLocation } from 'react-router-dom'

const titleMap: Record<string, string> = {
  '/': 'Operations Dashboard',
  '/camera-lab': 'Camera Configuration Lab',
  '/live': 'Live Camera Monitoring',
  '/violations': 'Violation Records',
  '/system-health': 'System Health',
}

export function TopNav() {
  const location = useLocation()
  const basePath = '/' + (location.pathname.split('/')[1] ?? '')
  const pageTitle = titleMap[basePath] ?? 'FootWatch Console'

  return (
    <header className="top-nav">
      <div className="top-nav-left">
        <p className="eyebrow">Objective 3 — Footpath Enforcement</p>
        <h1 className="page-title">{pageTitle}</h1>
      </div>
      <div className="top-nav-right">
        <span className="badge badge-accent">
          <span style={{ fontSize: '0.65rem' }}>●</span>
          Edge-First Pipeline
        </span>
        <span className="badge badge-neutral">v2.1</span>
      </div>
    </header>
  )
}
