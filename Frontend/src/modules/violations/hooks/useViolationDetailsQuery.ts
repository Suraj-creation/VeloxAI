import { useQuery } from '@tanstack/react-query'
import { getViolationDetails } from '@/modules/violations/api/getViolationDetails'

export function useViolationDetailsQuery(id: string | undefined) {
  return useQuery({
    queryKey: ['violation-details', id],
    queryFn: () => getViolationDetails(String(id)),
    enabled: Boolean(id),
  })
}
