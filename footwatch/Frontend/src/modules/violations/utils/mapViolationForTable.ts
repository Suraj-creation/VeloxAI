import { Violation } from '@/modules/violations/types/violation'
import { formatDateTime } from '@/shared/utils/date'
import { maskPlate } from '@/shared/utils/plate'
import { formatSpeed } from '@/shared/utils/speed'

export type ViolationTableRow = {
  id: string
  time: string
  plate: string
  cameraId: string
  vehicleClass: string
  speed: string
  confidence: string
  status: string
}

export function mapViolationForTable(item: Violation): ViolationTableRow {
  return {
    id: item.violation_id,
    time: formatDateTime(item.timestamp),
    plate: maskPlate(item.vehicle.plate_number),
    cameraId: item.location.camera_id ?? 'N/A',
    vehicleClass: item.vehicle.vehicle_class ?? 'N/A',
    speed: formatSpeed(item.vehicle.estimated_speed_kmph),
    confidence:
      typeof item.vehicle.plate_ocr_confidence === 'number'
        ? item.vehicle.plate_ocr_confidence.toFixed(2)
        : 'N/A',
    status: item.violation_status ?? 'UNKNOWN',
  }
}
