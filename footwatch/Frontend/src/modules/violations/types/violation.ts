import { z } from 'zod'

const challanSemanticSchema = z.object({
  violation_confirmed: z.boolean().optional(),
  vehicle_details: z
    .object({
      vehicle_type: z.string().optional(),
      vehicle_color: z.string().optional(),
      vehicle_description: z.string().optional(),
      license_plate: z.string().optional(),
      plate_confidence: z.number().optional(),
    })
    .default({}),
  violation_details: z
    .object({
      violation_type: z.string().optional(),
      severity: z.string().optional(),
      speed_kmph: z.number().optional(),
      location: z.string().optional(),
      timestamp: z.string().optional(),
    })
    .default({}),
  visual_analysis: z
    .object({
      footpath_detected: z.boolean().optional(),
      pedestrian_zone: z.boolean().optional(),
      rider_present: z.boolean().nullable().optional(),
      image_quality: z.string().optional(),
    })
    .default({}),
  legal_summary: z.string().optional(),
  confidence_scores: z
    .object({
      overall_confidence: z.number().optional(),
      vehicle_detection_confidence: z.number().optional(),
      plate_read_confidence: z.number().optional(),
    })
    .default({}),
})

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
      vehicle_highlighted: z.string().optional(),
      annotated_frame: z.string().optional(),
      full_frame: z.string().optional(),
      plate_crop_raw: z.string().optional(),
      plate_crop_enhanced: z.string().optional(),
      thumbnail: z.string().optional(),
    })
    .optional(),
  challan: z
    .object({
      status: z.string().optional(),
      download_ready: z.boolean().optional(),
      fine_amount_inr: z.number().optional(),
      provider: z.string().optional(),
      model: z.string().nullable().optional(),
      generated_at: z.string().optional(),
      manual_review_reason: z.string().nullable().optional(),
      evidence_image_type: z.string().nullable().optional(),
      evidence_image_path: z.string().nullable().optional(),
      pdf_path: z.string().nullable().optional(),
      json_path: z.string().nullable().optional(),
      generation_error: z.string().nullable().optional(),
      download_path: z.string().optional(),
      semantic_record: challanSemanticSchema.nullable().optional(),
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
