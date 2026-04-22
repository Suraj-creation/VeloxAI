import { useQuery } from '@tanstack/react-query'
import { listViolations, ViolationListQuery } from '@/modules/violations/api/listViolations'
import { polling } from '@/shared/config/polling'

export type ViolationFilterInput = ViolationListQuery

export function useViolationsQuery(filters: ViolationFilterInput) {
  return useQuery({
    queryKey: ['violations', filters],
    queryFn: () => listViolations(filters),
    refetchInterval: polling.violationsMs,
  })
}
