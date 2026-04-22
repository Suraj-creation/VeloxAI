import { ReactNode } from 'react'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorState } from '@/shared/components/ErrorState'

type DataStateProps = {
  isLoading: boolean
  error: unknown
  isEmpty: boolean
  emptyMessage: string
  children: ReactNode
}

export function DataState({ isLoading, error, isEmpty, emptyMessage, children }: DataStateProps) {
  if (isLoading) {
    return (
      <section className="state-card">
        <div className="loading-shimmer" style={{ height: '40px', marginBottom: '0.75rem' }} />
        <div className="loading-shimmer" style={{ height: '20px', width: '60%', margin: '0 auto' }} />
        <p className="muted" style={{ marginTop: '1rem', fontSize: '0.85rem' }}>Loading data...</p>
      </section>
    )
  }

  if (error) {
    return <ErrorState message={error instanceof Error ? error.message : 'Unexpected error'} />
  }

  if (isEmpty) {
    return <EmptyState title="No data available" subtitle={emptyMessage} />
  }

  return <>{children}</>
}
