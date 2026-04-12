import { z } from 'zod'

export const liveCameraSchema = z.object({
  camera_id: z.string(),
  location_name: z.string().default('Unknown location'),
  status: z.string().default('stale'),
  fps: z.number().nonnegative().optional(),
  latency_ms: z.number().nonnegative().optional(),
  reconnects: z.number().int().nonnegative().optional(),
  frame_failures: z.number().int().nonnegative().optional(),
  last_seen_ts: z.string().optional(),
})

export const liveCamerasResponseSchema = z.object({
  items: z.array(liveCameraSchema),
  next_cursor: z.string().optional(),
})

export type LiveCamera = z.infer<typeof liveCameraSchema>
export type LiveCamerasResponse = z.infer<typeof liveCamerasResponseSchema>
