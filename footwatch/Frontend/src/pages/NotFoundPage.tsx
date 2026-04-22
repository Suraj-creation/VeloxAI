import { Link } from 'react-router-dom'
import { AppShell } from '@/app/layout/AppShell'

export function NotFoundPage() {
  return (
    <AppShell>
      <section className="state-card" style={{ marginTop: '4rem' }}>
        <div style={{ fontSize: '3rem', marginBottom: '1rem', opacity: 0.3 }}>🔍</div>
        <h2>Route Not Found</h2>
        <p className="muted" style={{ marginTop: '0.5rem' }}>
          The page you requested does not exist in this build.
        </p>
        <Link to="/" className="btn-primary" style={{ display: 'inline-block', marginTop: '1.5rem' }}>
          ← Back to Dashboard
        </Link>
      </section>
    </AppShell>
  )
}
