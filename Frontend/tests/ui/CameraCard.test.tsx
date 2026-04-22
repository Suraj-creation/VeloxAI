import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { CameraCard } from '../../src/modules/live-cameras/components/CameraCard'

describe('CameraCard', () => {
  it('renders online camera status and attributes properly', () => {
    const mockCamera = {
      camera_id: 'cam-001',
      location_name: 'Main Junction',
      status: 'online',
      fps: 15.2,
      latency_ms: 120,
      reconnects: 2,
      last_seen_ts: new Date().toISOString() // Not stale
    }
    
    render(<CameraCard camera={mockCamera} />)
    
    expect(screen.getByText('cam-001')).toBeInTheDocument()
    expect(screen.getByText('Main Junction')).toBeInTheDocument()
    expect(screen.getByText('online')).toBeInTheDocument()
    expect(screen.getByText(/15.2/)).toBeInTheDocument()
    expect(screen.getByText(/120 ms/)).toBeInTheDocument()
  })

  it('marks correctly as stale if last seen is old', () => {
    const mockCamera = {
      camera_id: 'cam-002',
      location_name: 'Secondary Junction',
      status: 'online',
      last_seen_ts: new Date(Date.now() - 60000).toISOString() // 1 minute old
    }
    
    render(<CameraCard camera={mockCamera} />)
    expect(screen.getByText('stale')).toBeInTheDocument()
  })
})
