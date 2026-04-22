export function formatDateTime(value: string | undefined): string {
  if (!value) {
    return 'N/A'
  }

  const date = new Date(value)
  if (Number.isNaN(date.valueOf())) {
    return 'N/A'
  }

  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'medium',
  }).format(date)
}

export function ageMs(value: string | undefined): number {
  if (!value) {
    return Number.POSITIVE_INFINITY
  }

  const date = new Date(value)
  if (Number.isNaN(date.valueOf())) {
    return Number.POSITIVE_INFINITY
  }

  return Date.now() - date.getTime()
}
