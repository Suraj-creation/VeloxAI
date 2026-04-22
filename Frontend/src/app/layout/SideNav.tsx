import { NavLink } from 'react-router-dom'

const navItems = [
  { to: '/', label: 'Dashboard', icon: '📊' },
  { to: '/camera-lab', label: 'Camera Lab', icon: '🎛️' },
  { to: '/live', label: 'Live Cameras', icon: '📹' },
  { to: '/violations', label: 'Violations', icon: '🚨' },
  { to: '/system-health', label: 'System Health', icon: '💻' },
]

export function SideNav() {
  return (
    <nav className="side-nav" aria-label="Primary navigation">
      <div className="nav-brand">
        <div>
          <div className="nav-brand-dot" />
        </div>
        <div>
          <div className="nav-brand-text">FootWatch</div>
          <div className="nav-brand-sub">Edge AI Enforcement</div>
        </div>
      </div>

      <div className="nav-section-label">Operations</div>

      {navItems.map((item) => (
        <NavLink
          className={({ isActive }) =>
            isActive ? 'nav-link nav-link-active' : 'nav-link'
          }
          key={item.to}
          to={item.to}
        >
          <span className="nav-icon">{item.icon}</span>
          {item.label}
        </NavLink>
      ))}

      <div className="nav-section-label" style={{ marginTop: 'auto' }}>Models</div>
      <div className="nav-link" style={{ cursor: 'default', opacity: 0.6 }}>
        <span className="nav-icon">🎯</span>
        <span>
          <span style={{ fontSize: '0.78rem' }}>YOLOv8n</span>
          <span className="muted" style={{ display: 'block', fontSize: '0.65rem' }}>Two-Wheeler + LP</span>
        </span>
      </div>
      <div className="nav-link" style={{ cursor: 'default', opacity: 0.6 }}>
        <span className="nav-icon">🔍</span>
        <span>
          <span style={{ fontSize: '0.78rem' }}>PaddleOCR</span>
          <span className="muted" style={{ display: 'block', fontSize: '0.65rem' }}>PP-OCRv3 Engine</span>
        </span>
      </div>
    </nav>
  )
}
