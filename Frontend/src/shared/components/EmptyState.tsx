type EmptyStateProps = {
  title: string
  subtitle: string
}

export function EmptyState({ title, subtitle }: EmptyStateProps) {
  return (
    <section className="state-card">
      <div className="empty-icon">📭</div>
      <h3>{title}</h3>
      <p className="muted" style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>{subtitle}</p>
    </section>
  )
}
