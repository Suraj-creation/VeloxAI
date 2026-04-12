import { apiRequest } from '@/shared/api/client'
import { endpoints } from '@/shared/api/endpoints'
import { dashboardSummarySchema, DashboardSummary } from '@/modules/analytics/types/analytics'

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return apiRequest(endpoints.dashboardSummary, {
    schema: dashboardSummarySchema,
  })
}
