import { describe, it, expect } from 'vitest'
import { violationSchema } from '../../src/modules/violations/types/violation'

describe('Violation Schema Contract', () => {
  it('should successfully parse a valid full violation object', () => {
    const validData = {
      violation_id: 'v-1234567890-test',
      timestamp: '2026-04-12T10:00:00Z',
      violation_status: 'CONFIRMED_AUTO',
      fine_amount_inr: 500,
      location: {
        camera_id: 'cam-001',
        location_name: 'Main Street Crossing',
        gps_lat: 12.9716,
        gps_lng: 77.5946
      },
      vehicle: {
        plate_number: 'KA01AB1234',
        plate_ocr_confidence: 0.95,
        plate_format_valid: true,
        vehicle_class: 'motorcycle',
        estimated_speed_kmph: 45.2,
        track_id: 12
      },
      evidence: {
        full_frame: 's3://bucket/v-123.jpg',
        plate_crop_raw: 's3://bucket/v-123-plate.jpg',
        plate_crop_enhanced: 's3://bucket/v-123-plate-enh.jpg',
        thumbnail: 's3://bucket/v-123-thumb.jpg'
      }
    }

    const result = violationSchema.parse(validData)
    expect(result.violation_id).toBe('v-1234567890-test')
    expect(result.vehicle.plate_ocr_confidence).toBe(0.95)
  })

  it('should parse an object with missing optional fields using defaults', () => {
    const partialData = {
      violation_id: 'v-999',
      timestamp: '2026-04-12T10:00:00Z',
      location: {},
      vehicle: {}
    }

    const result = violationSchema.parse(partialData)
    expect(result.violation_status).toBe('CONFIRMED_AUTO')
    expect(result.fine_amount_inr).toBe(500)
    expect(result.evidence).toBeUndefined()
  })

  it('should throw an error for missing required fields', () => {
    const invalidData = {
      violation_id: 'v-123',
      // missing timestamp
      location: {},
      vehicle: {}
    }

    expect(() => violationSchema.parse(invalidData)).toThrow()
  })
})
