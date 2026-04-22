import { z } from 'zod'
import { apiRequest, unknownSchema } from '@/shared/api/client'
import { endpoints } from '@/shared/api/endpoints'
import { liveCameraSchema, liveCamerasResponseSchema, LiveCamerasResponse } from '@/modules/live-cameras/types/camera'

const arrayResponseSchema = z.array(liveCameraSchema)

export async function getLiveCameras(): Promise<LiveCamerasResponse> {
  const payload = await apiRequest(endpoints.liveCameras, { schema: unknownSchema })

  if (Array.isArray(payload)) {
    return { items: arrayResponseSchema.parse(payload) }
  }

  return liveCamerasResponseSchema.parse(payload)
}
