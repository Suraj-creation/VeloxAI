export function confidenceBadge(confidence: number | undefined): 'success' | 'warning' | 'danger' | 'neutral' {
  if (typeof confidence !== 'number') {
    return 'neutral'
  }

  if (confidence >= 0.8) {
    return 'success'
  }

  if (confidence >= 0.65) {
    return 'warning'
  }

  return 'danger'
}
