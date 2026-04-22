import { QueryProvider } from '@/app/providers/QueryProvider'
import { RouterProvider } from '@/app/providers/RouterProvider'
import { ThemeProvider } from '@/app/providers/ThemeProvider'
import { AppRoutes } from '@/app/routes/AppRoutes'

function App() {
  return (
    <ThemeProvider>
      <QueryProvider>
        <RouterProvider>
          <AppRoutes />
        </RouterProvider>
      </QueryProvider>
    </ThemeProvider>
  )
}

export default App
