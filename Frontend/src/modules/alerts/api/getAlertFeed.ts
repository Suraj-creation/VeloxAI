import { z } from 'zod'
import { apiRequest } from '@/shared/api/client'
import { endpoints } from '@/shared/api/endpoints'
import { alertSchema, AlertItem } from '@/modules/alerts/types/alert'

const alertArraySchema = z.array(alertSchema)
const alertFeedSchema = z.object({
  items: alertArraySchema,
})

export async function getAlertFeed(): Promise<AlertItem[]> {
  const payload = await apiRequest(endpoints.alerts, {
    schema: z.unknown(),
  })

  if (Array.isArray(payload)) {
    return alertArraySchema.parse(payload)
  }

  return alertFeedSchema.parse(payload).items
}
