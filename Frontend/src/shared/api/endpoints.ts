export const endpoints = {
  liveCameras: '/v1/live/cameras',
  violations: '/v1/violations',
  violationById: (id: string) => `/v1/violations/${id}`,
  violationEvidenceUrl: (id: string) => `/v1/violations/${id}/evidence-url`,
  dashboardSummary: '/v1/violations/summary',
  alerts: '/v1/alerts',
  edgeRuntimeStatus: '/v1/edge/live-preview',
  edgeRuntimeFrame: '/v1/edge/live-preview/frame',
  edgeConfig: '/v1/edge/config',
} as const
