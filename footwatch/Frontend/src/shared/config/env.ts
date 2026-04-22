import { z } from 'zod'

const envSchema = z.object({
  VITE_API_BASE_URL: z.string().url().default('http://localhost:8001'),
})

const parsed = envSchema.safeParse({
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
})

if (!parsed.success) {
  throw new Error(`Invalid environment configuration: ${parsed.error.message}`)
}

export const env = parsed.data
