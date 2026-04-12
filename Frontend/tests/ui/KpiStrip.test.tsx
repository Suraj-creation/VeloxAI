import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { KpiStrip } from '../../src/modules/analytics/components/KpiStrip'

describe('KpiStrip', () => {
  it('renders default values when data is undefined', () => {
    render(<KpiStrip data={undefined} />)
    
    expect(screen.getByText('Total Violations')).toBeInTheDocument()
    expect(screen.getByText('0')).toBeInTheDocument()
    
    expect(screen.getByText('Avg Speed')).toBeInTheDocument()
    expect(screen.getByText('0.0 km/h')).toBeInTheDocument()
    
    expect(screen.getByText('OCR Confidence')).toBeInTheDocument()
    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('renders formatted values from data', () => {
    const mockData = {
      total_violations: 154,
      unique_plates: 120,
      avg_speed_kmph: 45.67,
      avg_ocr_confidence: 0.885,
      by_class: {},
      by_hour: {}
    }
    
    render(<KpiStrip data={mockData} />)
    
    expect(screen.getAllByText('154').length).toBeGreaterThan(0)
    expect(screen.getAllByText('120').length).toBeGreaterThan(0)
    expect(screen.getAllByText('45.7 km/h').length).toBeGreaterThan(0)
    expect(screen.getAllByText('89%').length).toBeGreaterThan(0)
  })
})
