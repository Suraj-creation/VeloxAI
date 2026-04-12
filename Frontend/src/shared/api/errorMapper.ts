export type NormalizedApiError = {
  status: number
  code: string
  message: string
  requestId?: string
}

export function mapApiError(status: number, payload: unknown): NormalizedApiError {
  if (payload && typeof payload === 'object') {
    const value = payload as Record<string, unknown>
    return {
      status,
      code: String(value.code ?? 'api_error'),
      message: String(value.message ?? 'Request failed'),
      requestId: typeof value.request_id === 'string' ? value.request_id : undefined,
    }
  }

  return {
    status,
    code: 'api_error',
    message: 'Request failed',
  }
}
