export function formatSpeed(value: number | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return 'N/A'
  }

  return `${value.toFixed(1)} km/h`
}
