import { lazy, type ComponentType, type LazyExoticComponent } from 'react'

type RouteItem = {
  path: string
  component: LazyExoticComponent<ComponentType>
}

const DashboardPage = lazy(async () => ({ default: (await import('@/pages/DashboardPage')).DashboardPage }))
const CameraLabPage = lazy(async () => ({ default: (await import('@/pages/CameraLabPage')).CameraLabPage }))
const LivePage = lazy(async () => ({ default: (await import('@/pages/LivePage')).LivePage }))
const ViolationsPage = lazy(async () => ({ default: (await import('@/pages/ViolationsPage')).ViolationsPage }))
const ViolationDetailsPage = lazy(
  async () => ({ default: (await import('@/pages/ViolationDetailsPage')).ViolationDetailsPage }),
)
const SystemHealthPage = lazy(async () => ({ default: (await import('@/pages/SystemHealthPage')).SystemHealthPage }))
const NotFoundPage = lazy(async () => ({ default: (await import('@/pages/NotFoundPage')).NotFoundPage }))

export const routeConfig: RouteItem[] = [
  { path: '/', component: DashboardPage },
  { path: '/camera-lab', component: CameraLabPage },
  { path: '/live', component: LivePage },
  { path: '/violations', component: ViolationsPage },
  { path: '/violations/:id', component: ViolationDetailsPage },
  { path: '/system-health', component: SystemHealthPage },
  { path: '*', component: NotFoundPage },
]
