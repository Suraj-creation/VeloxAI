import { z } from 'zod'

const rawAlertSchema = z.object({
  id: z.string().optional(),
  alert_id: z.string().optional(),
  severity: z.enum(['info', 'warning', 'critical']),
  message: z.string(),
  timestamp: z.string().optional(),
  created_at: z.string().optional(),
})

export const alertSchema = rawAlertSchema.transform((value) => ({
  id: value.id ?? value.alert_id ?? `${value.severity}-${value.message}-${value.timestamp ?? value.created_at ?? 'na'}`,
  severity: value.severity,
  message: value.message,
  timestamp: value.timestamp ?? value.created_at ?? new Date().toISOString(),
}))

export type AlertItem = z.infer<typeof alertSchema>
