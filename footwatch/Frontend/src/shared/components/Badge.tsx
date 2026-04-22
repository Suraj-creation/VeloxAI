import { ReactNode } from 'react'
import { classNames } from '@/shared/utils/classNames'

type BadgeProps = {
  tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'info'
  children: ReactNode
}

export function Badge({ tone = 'neutral', children }: BadgeProps) {
  return <span className={classNames('badge', `badge-${tone}`)}>{children}</span>
}
