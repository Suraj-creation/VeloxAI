import { ChangeEvent } from 'react'
import { ViolationFilterInput } from '@/modules/violations/hooks/useViolationsQuery'

type ViolationFiltersProps = {
  value: ViolationFilterInput
  onChange: (next: ViolationFilterInput) => void
}

export function ViolationFilters({ value, onChange }: ViolationFiltersProps) {
  const handleText = (field: keyof ViolationFilterInput) => (event: ChangeEvent<HTMLInputElement>) => {
    onChange({ ...value, [field]: event.target.value || undefined })
  }

  const handleLimit = (event: ChangeEvent<HTMLInputElement>) => {
    const next = Number(event.target.value)
    onChange({ ...value, limit: Number.isNaN(next) ? 25 : next })
  }

  return (
    <div className="filter-bar" id="violation-filters">
      <input placeholder="Camera ID" value={value.camera_id ?? ''} onChange={handleText('camera_id')} />
      <input placeholder="Plate Number" value={value.plate ?? ''} onChange={handleText('plate')} />
      <input placeholder="Vehicle Class" value={value.class ?? ''} onChange={handleText('class')} />
      <input placeholder="Status" value={value.status ?? ''} onChange={handleText('status')} />
      <input type="number" min={1} max={200} placeholder="Limit" value={value.limit ?? 25} onChange={handleLimit} />
    </div>
  )
}
