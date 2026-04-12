import { useQuery } from '@tanstack/react-query'
import { getAlertFeed } from '@/modules/alerts/api/getAlertFeed'
import { polling } from '@/shared/config/polling'

export function useAlertFeedQuery() {
  return useQuery({
    queryKey: ['alerts'],
    queryFn: getAlertFeed,
    refetchInterval: polling.alertsMs,
  })
}
