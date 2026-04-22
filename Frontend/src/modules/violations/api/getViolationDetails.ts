import { apiRequest } from '@/shared/api/client'
import { endpoints } from '@/shared/api/endpoints'
import { Violation, violationSchema } from '@/modules/violations/types/violation'

export async function getViolationDetails(id: string): Promise<Violation> {
  return apiRequest(endpoints.violationById(id), {
    schema: violationSchema,
  })
}
