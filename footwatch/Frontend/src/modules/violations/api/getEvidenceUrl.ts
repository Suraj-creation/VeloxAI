import { apiRequest } from '@/shared/api/client'
import { endpoints } from '@/shared/api/endpoints'
import { evidenceUrlResponseSchema, EvidenceUrlResponse } from '@/modules/violations/types/violation'

export async function getEvidenceUrl(id: string, type = 'full_frame'): Promise<EvidenceUrlResponse> {
  return apiRequest(endpoints.violationEvidenceUrl(id), {
    query: { type },
    schema: evidenceUrlResponseSchema,
  })
}
