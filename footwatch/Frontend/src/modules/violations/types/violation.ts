import { z } from 'zod'

export const violationSchema = z.object({
  violation_id: z.string(),
  timestamp: z.string(),
  violation_status: z.string().optional().default('CONFIRMED_AUTO'),
  fine_amount_inr: z.number().optional().default(500),
  location: z.object({
    camera_id: z.string().optional(),
    location_name: z.string().optional(),
    gps_lat: z.number().optional(),
    gps_lng: z.number().optional(),
  }),
  vehicle: z.object({
    plate_number: z.string().optional(),
    plate_ocr_confidence: z.number().optional(),
    plate_format_valid: z.boolean().optional(),
    vehicle_class: z.string().optional(),
    estimated_speed_kmph: z.number().optional(),
    track_id: z.number().optional(),
  }),
  evidence: z
    .object({
      full_frame: z.string().optional(),
      plate_crop_raw: z.string().optional(),
      plate_crop_enhanced: z.string().optional(),
      thumbnail: z.string().optional(),
    })
    .optional(),
})

export const violationListResponseSchema = z.object({
  items: z.array(violationSchema),
  next_cursor: z.string().optional(),
})

export const evidenceUrlResponseSchema = z.object({
  url: z.string().url(),
  expires_at: z.string(),
})

export type Violation = z.infer<typeof violationSchema>
export type ViolationListResponse = z.infer<typeof violationListResponseSchema>
export type EvidenceUrlResponse = z.infer<typeof evidenceUrlResponseSchema>
