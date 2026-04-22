import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ViolationFilters } from '@/modules/violations/components/ViolationFilters'

describe('ViolationFilters', () => {
  it('emits updated filters when camera id changes', () => {
    const onChange = vi.fn()

    render(<ViolationFilters value={{ limit: 25 }} onChange={onChange} />)

    fireEvent.change(screen.getByPlaceholderText('Camera ID'), {
      target: { value: 'FP_CAM_009' },
    })

    expect(onChange).toHaveBeenCalled()
    expect(onChange.mock.calls[0][0].camera_id).toBe('FP_CAM_009')
  })
})
