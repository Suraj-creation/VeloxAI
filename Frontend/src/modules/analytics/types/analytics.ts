import { z } from 'zod'

export const dashboardSummarySchema = z.object({
  total_violations: z.number().int().nonnegative().default(0),
  unique_plates: z.number().int().nonnegative().default(0),
  avg_speed_kmph: z.number().nonnegative().default(0),
  avg_ocr_confidence: z.number().nonnegative().default(0),
  by_class: z.record(z.string(), z.number()).optional().default({}),
  by_hour: z.record(z.string(), z.number()).optional().default({}),
})

export type DashboardSummary = z.infer<typeof dashboardSummarySchema>
