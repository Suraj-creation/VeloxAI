import { z, ZodType } from 'zod'
import { env } from '@/shared/config/env'
import { mapApiError } from '@/shared/api/errorMapper'

type Primitive = string | number | boolean

type RequestOptions<T> = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  query?: Record<string, Primitive | undefined>
  body?: unknown
  schema?: ZodType<T>
  signal?: AbortSignal
  headers?: HeadersInit
}

export class ApiRequestError extends Error {
  status: number
  code: string
  requestId?: string

  constructor(status: number, code: string, message: string, requestId?: string) {
    super(message)
    this.status = status
    this.code = code
    this.requestId = requestId
  }
}

function toQueryString(query: Record<string, Primitive | undefined>) {
  const params = new URLSearchParams()

  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined) {
      params.set(key, String(value))
    }
  })

  const raw = params.toString()
  return raw ? `?${raw}` : ''
}

export async function apiRequest<T = unknown>(path: string, options: RequestOptions<T> = {}): Promise<T> {
  const method = options.method ?? 'GET'
  const query = options.query ? toQueryString(options.query) : ''
  const url = `${env.VITE_API_BASE_URL}${path}${query}`

  const response = await fetch(url, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  })

  if (!response.ok) {
    let payload: unknown = null
    try {
      payload = await response.json()
    } catch {
      payload = null
    }

    const normalized = mapApiError(response.status, payload)
    throw new ApiRequestError(normalized.status, normalized.code, normalized.message, normalized.requestId)
  }

  if (response.status === 204) {
    return {} as T
  }

  const rawBody = (await response.json()) as unknown
  const body =
    rawBody && typeof rawBody === 'object' && 'data' in rawBody
      ? (rawBody as { data: unknown }).data
      : rawBody

  if (!options.schema) {
    return body as T
  }

  return options.schema.parse(body)
}

export const unknownSchema = z.unknown()
