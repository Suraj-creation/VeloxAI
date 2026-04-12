import { z } from 'zod'
import { apiRequest, unknownSchema } from '@/shared/api/client'
import { endpoints } from '@/shared/api/endpoints'
import { ViolationListResponse, violationListResponseSchema, violationSchema } from '@/modules/violations/types/violation'

export type ViolationListQuery = {
  camera_id?: string
  plate?: string
  class?: string
  status?: string
  from?: string
  to?: string
  limit?: number
  cursor?: string
}

const violationArraySchema = z.array(violationSchema)

export async function listViolations(query: ViolationListQuery = {}): Promise<ViolationListResponse> {
  const payload = await apiRequest(endpoints.violations, {
    query,
    schema: unknownSchema,
  })

  if (Array.isArray(payload)) {
    return { items: violationArraySchema.parse(payload) }
  }

  return violationListResponseSchema.parse(payload)
}
