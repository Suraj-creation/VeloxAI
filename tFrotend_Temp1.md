# Frontend Modular Development Plan (Temp 1)

## 1) Requirement Understanding Consolidated

Project target for website:
- Build a robust operations dashboard website in Frontend folder.
- Integrate with Objective 3 enforcement pipeline outputs and telemetry.
- Follow free-tier-first AWS architecture from tech stack.
- Show live camera state, confirmed violations, evidence, and analytics.
- Support filtering, details page, evidence preview, and operational health visibility.

Objective 3 enforcement constraints that frontend must respect:
- Only confirmed violations are persistent records.
- Non-violation detections must not become complaint records.
- Full-frame enforcement logic is backend and edge concern, but UI should clearly communicate that policy.
- Plate confidence and validation should be visible for operator trust.
- Low-confidence and manual review concepts must be represented in UI states.

Tech stack constraints:
- React + TypeScript (Vite).
- TanStack Query for API state.
- Recharts for analytics.
- Deployable to S3 + CloudFront.
- Polling model, not websocket-first for MVP.
- React Router for route orchestration.
- Zod-based runtime response validation at API boundary.
- Vitest + Testing Library + Playwright for layered test confidence.

## 2) Frontend Folder Structure (Modular)

Frontend/
- src/
	- app/
		- providers/
			- QueryProvider.tsx
			- ThemeProvider.tsx
			- RouterProvider.tsx
		- routes/
			- AppRoutes.tsx
			- routeConfig.ts
		- layout/
			- AppShell.tsx
			- TopNav.tsx
			- SideNav.tsx
			- StatusBar.tsx
	- modules/
		- live-cameras/
			- api/
				- getLiveCameras.ts
			- hooks/
				- useLiveCamerasQuery.ts
			- components/
				- CameraHealthGrid.tsx
				- CameraCard.tsx
			- types/
				- camera.ts
		- violations/
			- api/
				- listViolations.ts
				- getViolationDetails.ts
				- getEvidenceUrl.ts
			- hooks/
				- useViolationsQuery.ts
				- useViolationDetailsQuery.ts
			- components/
				- ViolationsTable.tsx
				- ViolationFilters.tsx
				- ViolationCard.tsx
				- ViolationDetailPanel.tsx
				- EvidenceViewer.tsx
			- types/
				- violation.ts
			- utils/
				- mapViolationForTable.ts
				- confidenceBadge.ts
		- analytics/
			- api/
				- getDashboardSummary.ts
			- hooks/
				- useDashboardSummaryQuery.ts
			- components/
				- KpiStrip.tsx
				- ViolationsByHourChart.tsx
				- VehicleClassChart.tsx
				- OcrConfidenceChart.tsx
			- types/
				- analytics.ts
		- alerts/
			- api/
				- getAlertFeed.ts
			- components/
				- AlertTicker.tsx
			- types/
				- alert.ts
	- shared/
		- api/
			- client.ts
			- endpoints.ts
			- errorMapper.ts
		- components/
			- DataState.tsx
			- EmptyState.tsx
			- ErrorState.tsx
			- Badge.tsx
			- Pill.tsx
		- config/
			- env.ts
			- polling.ts
		- utils/
			- date.ts
			- speed.ts
			- plate.ts
			- classNames.ts
	- pages/
		- DashboardPage.tsx
		- ViolationsPage.tsx
		- ViolationDetailsPage.tsx
		- LivePage.tsx
		- SystemHealthPage.tsx
		- NotFoundPage.tsx
	- styles/
		- tokens.css
		- base.css
		- layout.css
		- motion.css
		- utilities.css
	- main.tsx
- public/
	- icons/
	- brand/
- tests/
	- contract/
	- ui/
	- e2e/

## 3) Frontend Module Responsibilities

Module: app shell
- Own routing, global providers, role guard extension point, and shell chrome.

Module: live-cameras
- Show near-realtime camera health snapshots and transient telemetry.
- Poll every 2 to 5 seconds.

Module: violations
- Core operational workflow.
- Server-side filters by time window, camera, vehicle class, plate, and confidence bands.
- Progressive evidence loading through signed URL endpoint.

Module: analytics
- Aggregate trend and KPI visualizations over selected time windows.

Module: alerts
- Optional feed for critical system events and high-risk violation events.

Module: shared
- Centralized API client, error handling, environment policy, and reusable primitives.

## 4) Contract First API Expectations

Frontend will consume these endpoints from backend:
- POST /v1/telemetry
- POST /v1/violations
- POST /v1/violations/{id}/evidence-complete
- GET /v1/live/cameras
- GET /v1/violations
- GET /v1/violations/{id}
- GET /v1/violations/{id}/evidence-url

Frontend read paths for MVP:
- GET /v1/live/cameras
- GET /v1/violations with query parameters
- GET /v1/violations/{id}
- GET /v1/violations/{id}/evidence-url

Contract governance rules:
- API versioning remains path-based and additive for backward compatibility.
- Pagination contract must be stable and explicit (cursor token preferred over page number for growth).
- Time fields must be ISO-8601 UTC in payloads and rendered with timezone awareness in UI.
- Unknown enum values must degrade gracefully to "unknown" badge without view breakage.
- Every API error payload must contain request_id for operator incident tracing.

## 5) Frontend Delivery Phases

Phase F1: baseline scaffold
- Create Vite React TypeScript app under Frontend.
- Add routing, query provider, strict linting, and environment loader.
- Add style token system and responsive shell layout.

Phase F2: API contract client layer
- Build typed client wrapper and runtime response guards.
- Implement query key factory and polling defaults.
- Add global error normalization.

Phase F3: live operations screen
- Live camera grid with status, fps, latency, reconnect counts, and last seen.
- Auto-refresh and stale marker behavior.

Phase F4: violations module
- Filterable table with pagination and quick detail panel.
- Detail page with evidence tabs and metadata JSON view.
- Confidence and validation badges.

Phase F5: analytics module
- KPI strip and hourly trends.
- Class distribution and OCR confidence distribution.

Phase F6: production hardening
- Loading and error states for each region.
- Keyboard accessibility and focus order checks.
- Empty states for no camera data and no violations.
- Build-time environment validation and route fallback strategy for CloudFront.

## 6) UI Behavior and State Rules

Live refresh rules:
- Live cameras polling interval: default 3 seconds.
- Violations polling interval: default 5 seconds.
- Backoff to 10 to 15 seconds on repeated network failures.

Evidence handling:
- Never persist presigned links in local storage.
- Fetch signed URL on demand when evidence pane opens.

Data policy alignment:
- Do not render unconfirmed detections as violations.
- Distinguish telemetry from violation evidence in UI labels.

Cache and consistency rules:
- Use stale-while-revalidate pattern for list views to preserve operator continuity.
- Invalidate violation detail query after evidence URL fetch only when evidence state changes.
- Keep poll timers centralized in shared config to avoid hidden module-level drift.
- Do not cache presigned evidence URLs beyond their expiry window.

## 7) Testing Strategy for Frontend

Unit tests:
- Query hooks and data mappers.
- Badge and threshold display logic.

Contract tests:
- Validate parser behavior against mocked endpoint payloads.

Component tests:
- Violations table filter behavior.
- Evidence viewer loading and error paths.

E2E smoke:
- Open dashboard.
- Validate live cards load.
- Filter violations.
- Open one violation details and preview evidence.

Quality thresholds:
- Unit plus component coverage minimum 80 percent lines and 75 percent branches for core modules.
- Contract test suite must pass against backend OpenAPI examples before merge.
- Playwright smoke suite must pass in CI for desktop and mobile viewport profiles.

## 8) Frontend Risks and Mitigation

Risk: stale telemetry and false operator confidence.
- Mitigation: display freshness timestamps and stale states.

Risk: heavy images affecting UX on low bandwidth.
- Mitigation: thumbnail-first strategy and lazy evidence fetch.

Risk: API schema drift during backend iteration.
- Mitigation: shared OpenAPI contract and typed parsers with strict guards.

## 9) Frontend Definition of Done

- Dashboard renders live camera health, recent violations, and key analytics.
- Filters and details workflows are fully functional.
- Responsive behavior verified on desktop and mobile.
- Accessibility baseline passes keyboard and semantic checks.
- Build artifact is ready for S3 and CloudFront deployment.
- All core tests pass in CI.
- Web Vitals targets on operator hardware are met: LCP under 2.5 seconds, CLS under 0.1, INP under 200 ms.
- Error boundary and fallback states exist for every route-level data dependency.
- Security headers and CSP are validated in deployed environment.
- Rollback deployment path is documented and rehearsed once before production cutover.

## 10) Immediate Build Start Checklist

1. Scaffold Frontend Vite app with TypeScript.
2. Add app shell and provider stack.
3. Implement shared API client and endpoint map.
4. Deliver live-cameras module first.
5. Deliver violations module second.
6. Deliver analytics module third.
7. Run tests and produce first deployment build.

## 11) Production Non-Functional Requirements

Performance and responsiveness:
- First dashboard render should complete under 3 seconds on a typical police operations network.
- Violation table interactions (filter apply, sort, page change) should respond under 300 ms after data arrives.

Availability expectations:
- Frontend uptime target: 99.5 percent monthly for MVP.
- Graceful degradation mode: show last successful data snapshot when backend is temporarily unavailable.

Accessibility baseline:
- Target WCAG 2.2 AA for color contrast, keyboard navigation, focus visibility, and semantic labeling.

## 12) Production Security and Privacy Controls

Client-side security:
- Enforce strict Content Security Policy compatible with CloudFront hosted app.
- Disable inline script patterns and avoid dynamic code execution.
- Sanitize any server-provided rich text before rendering.

Privacy controls:
- Avoid storing personally identifiable evidence data in browser storage.
- Keep logs free of full plate numbers in client diagnostics where possible; mask plate in UI telemetry logs.

## 13) Observability and Incident Diagnostics

Frontend telemetry:
- Emit structured UI events for route load, API errors, evidence view failures, and polling drift.
- Capture request_id from backend error payload and surface it in operator-facing error drawers.

Monitoring dashboards:
- Build minimal dashboard for frontend error rate, failed API percentage, and median render latency.

## 14) CI/CD and Release Controls

Pipeline stages:
- Lint and typecheck.
- Unit plus component tests.
- Contract tests against OpenAPI snapshots.
- Playwright smoke tests.
- Production build and artifact checksum.

Release strategy:
- Blue-green CloudFront distribution switch or immutable S3 versioned artifacts.
- Fast rollback path to previous static artifact version.

## 15) Launch Plan and Rollout Strategy

Rollout waves:
1. Internal QA with seeded data and synthetic API responses.
2. Staging with real backend in read-only operator pilot mode.
3. Production limited camera set (assisted mode supervision).
4. Full rollout with incident watch window and daily review.

Exit criteria per wave:
- No P0 or P1 defects open.
- API contract drift count equals zero.
- Accessibility and smoke suites pass on each release candidate.

## 16) Frontend Production Risks Added

Risk: Polling storms during backend partial outage.
- Mitigation: exponential backoff, jitter, and global max concurrent polling budget.

Risk: Operator confusion between stale and live states.
- Mitigation: explicit freshness badges, stale banners, and last successful update timestamps.

Risk: Evidence URL expiry during long review sessions.
- Mitigation: automatic refetch with explicit expiry messaging and retry action.

## 17) Requirement Traceability Matrix

Objective and stack requirement: show live camera status and telemetry
- Planned module: live-cameras plus analytics plus app status bar
- Verification: live cards poll correctly and show stale state when backend pauses

Objective and stack requirement: show only confirmed violations as enforcement records
- Planned module: violations list and detail mapping rules
- Verification: no unconfirmed telemetry item appears in violation views

Objective and stack requirement: evidence preview with secure access
- Planned module: EvidenceViewer with on-demand signed URL fetch
- Verification: evidence loads via signed URL and fails safely on expiry

Objective and stack requirement: low-confidence and manual review visibility
- Planned module: violations badges and filter controls
- Verification: review-required items are clearly tagged and filterable

Objective and stack requirement: deploy on S3 plus CloudFront
- Planned module: CI/CD release controls and static build pipeline
- Verification: build artifact deploys with rollback-ready versioned assets

Objective and stack requirement: free-tier-safe polling architecture
- Planned module: shared polling config, backoff, and jitter policy
- Verification: controlled request volume under outage simulation

