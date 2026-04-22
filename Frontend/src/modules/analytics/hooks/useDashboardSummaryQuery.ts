import { useQuery } from '@tanstack/react-query'
import { getDashboardSummary } from '@/modules/analytics/api/getDashboardSummary'
import { polling } from '@/shared/config/polling'

export function useDashboardSummaryQuery() {
  return useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: getDashboardSummary,
    refetchInterval: polling.summaryMs,
  })
}
