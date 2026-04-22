import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = fileURLToPath(new URL('.', import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(rootDir, './src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined
          }

          if (/[\\/]node_modules[\\/]recharts[\\/]/.test(id)) {
            return 'vendor-charts'
          }

          if (/[\\/]node_modules[\\/]@tanstack[\\/]react-query[\\/]/.test(id)) {
            return 'vendor-query'
          }

          if (/[\\/]node_modules[\\/]react-router(?:-dom)?[\\/]/.test(id)) {
            return 'vendor-router'
          }

          if (/[\\/]node_modules[\\/]zod[\\/]/.test(id)) {
            return 'vendor-zod'
          }

          if (/[\\/]node_modules[\\/]react(?:-dom)?[\\/]/.test(id)) {
            return 'vendor-react'
          }

          return 'vendor-misc'
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/ui/**/*.test.tsx', 'tests/contract/**/*.test.ts'],
  },
})
