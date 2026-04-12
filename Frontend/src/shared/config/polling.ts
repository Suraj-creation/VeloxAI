export const polling = {
  liveCamerasMs: 3_000,
  violationsMs: 5_000,
  summaryMs: 10_000,
  alertsMs: 10_000,
  retryBackoffMs: [10_000, 15_000],
} as const
