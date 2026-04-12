import { Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import { routeConfig } from '@/app/routes/routeConfig'

export function AppRoutes() {
  return (
    <Routes>
      {routeConfig.map((route) => (
        <Route
          key={route.path}
          path={route.path}
          element={
            <Suspense
              fallback={
                <section className="state-card">
                  <h3>Loading route...</h3>
                </section>
              }
            >
              <route.component />
            </Suspense>
          }
        />
      ))}
    </Routes>
  )
}
