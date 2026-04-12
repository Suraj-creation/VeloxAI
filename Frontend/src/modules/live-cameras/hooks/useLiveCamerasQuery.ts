import { useQuery } from '@tanstack/react-query'
import { getLiveCameras } from '@/modules/live-cameras/api/getLiveCameras'
import { polling } from '@/shared/config/polling'

export function useLiveCamerasQuery() {
  return useQuery({
    queryKey: ['live-cameras'],
    queryFn: getLiveCameras,
    refetchInterval: polling.liveCamerasMs,
  })
}
