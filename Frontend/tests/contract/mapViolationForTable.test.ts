import { describe, expect, it } from 'vitest'
import { mapViolationForTable } from '@/modules/violations/utils/mapViolationForTable'
import { Violation } from '@/modules/violations/types/violation'

describe('mapViolationForTable', () => {
  it('maps a violation to a safe table row', () => {
    const violation: Violation = {
      violation_id: 'v-1',
      timestamp: '2026-01-01T12:00:00Z',
      violation_status: 'CONFIRMED_AUTO',
      fine_amount_inr: 500,
      location: {
        camera_id: 'FP_CAM_001',
      },
      vehicle: {
        plate_number: 'KA05AB1234',
        vehicle_class: 'motorcycle',
        estimated_speed_kmph: 21.4,
        plate_ocr_confidence: 0.91,
      },
    }

    const row = mapViolationForTable(violation)

    expect(row.id).toBe('v-1')
    expect(row.cameraId).toBe('FP_CAM_001')
    expect(row.plate).toBe('KA****34')
    expect(row.status).toBe('CONFIRMED_AUTO')
  })
})
