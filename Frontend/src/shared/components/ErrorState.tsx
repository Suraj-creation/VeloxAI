type ErrorStateProps = {
  message: string
}

export function ErrorState({ message }: ErrorStateProps) {
  return (
    <section className="state-card state-card-error">
      <div className="empty-icon">⚠️</div>
      <h3 className="text-danger">Error</h3>
      <p className="muted" style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>{message}</p>
    </section>
  )
}
