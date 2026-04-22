import { ReactNode } from 'react'

type PillProps = {
  label: ReactNode
}

export function Pill({ label }: PillProps) {
  return <span className="pill">{label}</span>
}
