export function formatPlate(value: string | undefined): string {
  if (!value) {
    return 'UNKNOWN'
  }

  return value.replace(/\s+/g, '').toUpperCase()
}

export function maskPlate(value: string | undefined): string {
  const plate = formatPlate(value)
  if (plate.length < 4) {
    return plate
  }

  return `${plate.slice(0, 2)}****${plate.slice(-2)}`
}
