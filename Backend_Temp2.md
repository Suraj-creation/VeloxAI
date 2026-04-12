# Backend Modular Development Plan (Temp 2)

## 1) Requirement Understanding Consolidated

Backend target:
- Build robust API and processing backbone in Backend folder.
- Keep edge inference local and only ingest telemetry plus confirmed violation metadata.
- Store evidence in object storage and metadata in DynamoDB.
- Use free-tier-first AWS architecture.
- Support dashboard reads with low latency and resilient writes.

Non-negotiable policy from Objective 3:
- Persist only confirmed violations and related evidence.
- Keep live telemetry ephemeral with TTL.
- Support manual review path for low-confidence OCR cases.
- Ensure dedup and cooldown behavior are enforceable by API contract and idempotency.

## 2) Backend Folder Structure (Modular)

Backend/
- infra/
	- terraform/
		- providers.tf
		- variables.tf
		- outputs.tf
		- api_gateway.tf
		- lambda.tf
		- dynamodb.tf
		- s3.tf
		- sqs.tf
		- iam.tf
		- cloudwatch.tf
	- sam/
		- template.yaml
- services/
	- common/
		- config.py
		- logger.py
		- errors.py
		- auth.py
		- idempotency.py
		- response.py
		- validators.py
	- contracts/
		- openapi.yaml
		- schemas/
			- telemetry_ingest.json
			- violation_ingest.json
			- violation_record.json
			- live_camera_state.json
	- ingest_api/
		- app.py
		- handlers/
			- post_telemetry.py
			- post_violation.py
			- post_evidence_complete.py
		- repositories/
			- camera_live_state_repo.py
			- violation_queue_repo.py
			- idempotency_repo.py
		- tests/
			- test_post_telemetry.py
			- test_post_violation.py
	- query_api/
		- app.py
		- handlers/
			- get_live_cameras.py
			- list_violations.py
			- get_violation_details.py
			- get_evidence_url.py
		- repositories/
			- live_state_read_repo.py
			- violations_read_repo.py
			- evidence_repo.py
		- tests/
			- test_get_live_cameras.py
			- test_list_violations.py
	- workers/
		- process_violation_queue/
			- handler.py
			- services/
				- violation_normalizer.py
				- violation_persister.py
				- alert_publisher.py
			- tests/
				- test_worker_happy_path.py
				- test_worker_retries.py
	- local_dev/
		- docker-compose.yml
		- seed_data.py
		- dynamodb_local/
		- localstack/
- docs/
	- runbooks/
		- deploy.md
		- rollback.md
		- incident_response.md
	- api/
		- examples.md

Infrastructure decision lock:
- Terraform is primary for repeatable environment provisioning.
- SAM template remains optional for local packaging and quick developer emulation only.

## 3) Logical Module Responsibilities

Module: ingest API
- Accept edge telemetry and violation metadata.
- Perform schema validation and idempotency checks.
- Write telemetry directly to CameraLiveState with TTL.
- Enqueue violations to SQS for asynchronous processing.

Module: worker
- Consume SQS messages.
- Normalize and enrich violation records.
- Persist to Violations table.
- Optionally publish notifications through SNS.

Module: query API
- Serve dashboard reads for live camera state, violation listing, and violation details.
- Generate presigned evidence links.

Module: contracts
- Single source of truth for request and response schemas.
- Keep frontend and backend in lockstep via OpenAPI.

Module: common
- Shared cross-cutting concerns such as logging, errors, validation, and idempotency utilities.

Module: infra
- Provision API Gateway, Lambda, DynamoDB, S3, SQS, IAM, CloudWatch.

## 4) Data Model Plan

Table: CameraLiveState
- PK: camera_id
- Attributes: last_seen_ts, fps, latency_ms, reconnects, frame_failures, mode, location, status
- TTL attribute: expires_at in 120 to 300 seconds
- Purpose: transient operational state only

Table: Violations
- PK: violation_id
- Core attributes: event_ts, camera_id, plate_number, vehicle_class, speed_kmph, ocr_confidence, plate_valid, fine_amount, evidence_paths
- Lifecycle attributes: violation_status, review_required, review_reason, evidence_status, processing_attempts
- Audit attributes: created_at, updated_at, source_request_id, idempotency_key_hash, model_version
- GSI1: camera_id + event_ts
- GSI2: plate_number + event_ts
- Optional GSI3: location_name + event_ts

Table: IdempotencyRecords
- PK: idempotency_key
- Attributes: request_hash, first_seen_at, response_snapshot, expires_at
- TTL attribute: expires_at in 24 to 72 hours (configurable)
- Purpose: prevent duplicate violation creation under edge retries and network replay

Bucket: footwatch-evidence
- Prefixes:
	- evidence/full_frame/
	- evidence/plate_raw/
	- evidence/plate_enhanced/
	- evidence/thumbnail/
- Lifecycle: move old objects to lower-cost class and then expire by retention policy.

Queues:
- violation_ingest_queue
- violation_dlq

## 5) API Contract Plan

Write endpoints:
- POST /v1/telemetry
- POST /v1/violations
- POST /v1/violations/{id}/evidence-complete

Read endpoints:
- GET /v1/live/cameras
- GET /v1/violations
- GET /v1/violations/{id}
- GET /v1/violations/{id}/evidence-url

Cross-cutting endpoint rules:
- Include request_id in response metadata.
- Return deterministic error codes and machine-readable error payloads.
- Require idempotency key for violation creation.
- Enforce strict request size limits to protect Lambda and API Gateway budgets.
- Use cursor-based pagination for list endpoints at scale.
- Return consistent UTC timestamps in ISO-8601 format.
- Add explicit API error catalog with stable numeric and string codes.

Authentication and authorization rules:
- Edge ingest uses signed credentials flow (STS-issued temporary credentials or scoped API key during MVP).
- Dashboard read endpoints require authenticated operator role with least privilege policy.
- Evidence URL generation must verify caller authorization before signing.

## 6) Backend Delivery Phases

Phase B1: contract and skeleton
- Define OpenAPI and JSON schemas.
- Scaffold ingest API, query API, and worker packages.
- Add shared logger, config loader, and error mapping.

Phase B2: ingest path
- Implement telemetry ingestion with TTL write.
- Implement violation ingestion to SQS with idempotency checks.
- Add evidence completion endpoint update path.

Phase B3: worker path
- Implement queue consumer to persist final violation records.
- Implement DLQ and retry-safe processing.
- Add optional SNS publish plugin.

Phase B4: query path
- Implement live cameras read endpoint.
- Implement violations search and detail endpoints.
- Implement presigned evidence URL endpoint.

Phase B5: infra and deployment
- Provision infra modules using Terraform or SAM.
- Configure IAM least privilege.
- Configure CloudWatch logs, metrics, and alarms.

Phase B6: hardening
- Add request validation middleware and strict schema enforcement.
- Add rate limiting strategy at API Gateway level.
- Add structured audit logging for enforcement-sensitive operations.

Phase B7: production readiness gate
- Execute load and chaos smoke for queue backlog and partial dependency failure.
- Validate backup and restore path for DynamoDB and S3 evidence metadata.
- Rehearse rollback and verify no data-loss regression on deploy rollback.

## 7) Reliability and Security Plan

Reliability:
- Use SQS decoupling so ingest remains fast under spikes.
- Use DLQ and replay tooling.
- Enforce idempotent create semantics for repeated edge retries.

Security:
- Use IAM least privilege by function.
- Sign evidence access through short-lived presigned URLs.
- Keep sensitive values in parameter store or secrets manager.
- Deny public bucket listing and direct object exposure.

Operational visibility:
- CloudWatch dashboards for p95 latency, error rates, queue depth, and DLQ count.
- Alerts for sustained API errors and queue backlogs.

Operational runbook minimums:
- DLQ replay procedure with safety checks.
- Evidence signing outage fallback behavior.
- Hotfix rollback steps with data integrity verification.

## 8) Testing Strategy for Backend

Unit tests:
- Validators, idempotency utilities, and repository adapters.

Contract tests:
- Ensure request and response payload conformance against schemas.

Integration tests:
- Ingest API to SQS to worker to DynamoDB flow.
- Query API reads from seeded records.

Failure tests:
- Malformed payload rejection.
- Duplicate violation idempotency behavior.
- Worker retry and DLQ routing behavior.

Load smoke:
- Simulate telemetry for multiple cameras with realistic polling intervals.

Release gates:
- Contract tests must pass against OpenAPI and JSON schema snapshots.
- Integration tests must pass on ephemeral environment before deployment.
- No critical security findings open at release cut.

## 9) Backend Risks and Mitigation

Risk: evidence and metadata drift due to async timing.
- Mitigation: evidence-complete endpoint and status transitions.

Risk: duplicate violations due to edge retries.
- Mitigation: idempotency key plus deterministic violation identity policy.

Risk: free-tier quota exhaustion.
- Mitigation: retention limits, polling guardrails, and request shaping.

Risk: noisy low-confidence OCR data.
- Mitigation: manual review state and confidence thresholds in query filters.

Risk: hot partition pressure on Violations table during burst traffic.
- Mitigation: partition key strategy review, adaptive write patterns, and monitored consumed capacity alarms.

Risk: runaway evidence storage growth.
- Mitigation: S3 lifecycle expiry, compression policy, and retention governance by environment.

## 10) Backend Definition of Done

- Ingest, queue processing, and query APIs are fully functional.
- DynamoDB, S3, SQS, and API Gateway integration is validated end to end.
- Presigned evidence retrieval works from frontend.
- Alerting and logs provide actionable operational diagnostics.
- Security baseline and least privilege policy are enforced.
- Automated test suite passes in CI.
- SLO dashboards and alarms are live and verified with synthetic checks.
- Runbooks are tested by one non-author engineer before production sign-off.
- Security review of IAM policies and bucket access completes with no high-risk exceptions.

## 11) Immediate Build Start Checklist

1. Create backend contract package and OpenAPI file first.
2. Scaffold ingest API and shared libraries.
3. Implement telemetry and violation ingest handlers.
4. Implement SQS worker and persistence logic.
5. Implement dashboard query handlers.
6. Provision minimal AWS infra and deploy dev stage.
7. Validate complete edge to backend to frontend flow.

## 12) Backend Production SLO and Capacity Targets

Availability and latency:
- Ingest API availability target: 99.5 percent monthly.
- Query API availability target: 99.5 percent monthly.
- P95 ingest write acknowledgment latency under 300 ms.
- P95 query latency under 500 ms for common dashboard filters.

Processing targets:
- SQS worker average queue delay under 5 seconds during normal load.
- DLQ rate under 0.1 percent of processed messages.

## 13) Violation Lifecycle State Machine

Proposed states:
- RECEIVED: accepted by ingest API and queued.
- PROCESSING: worker is enriching and validating payload.
- EVIDENCE_PENDING: violation exists but evidence completion not confirmed.
- CONFIRMED_AUTO: meets confidence policy and is auto-actionable.
- REQUIRES_REVIEW: low-confidence or validation mismatch flagged for manual review.
- REJECTED: invalid or duplicate after policy evaluation.

State transition rules:
- Evidence URL endpoints only available from CONFIRMED_AUTO and REQUIRES_REVIEW states.
- REJECTED entries remain auditable but excluded from default operator list queries.

## 14) Data Governance and Retention Policy

Retention windows by environment:
- Dev: short retention for cost control (example 7 to 14 days evidence).
- Staging: medium retention for test audits (example 14 to 30 days).
- Production: policy-driven legal retention with explicit expiry workflow.

Data integrity controls:
- Store checksum or etag metadata for each evidence object.
- Persist linkage between metadata record and evidence object keys.

## 15) Security Hardening Plan

IAM:
- Function-specific roles with deny-by-default stance.
- No wildcard resource permissions unless justified and reviewed.

API protection:
- API Gateway throttling, WAF optional shield, and request schema validation.
- Input sanitization and canonical validation before persistence.

Secrets:
- Parameter Store or Secrets Manager for runtime secrets.
- Rotation policy documented for sensitive credentials.

## 16) CI/CD and Environment Promotion

Environment progression:
1. Local and contract tests.
2. Ephemeral integration stack.
3. Shared staging.
4. Production with controlled rollout.

Promotion rules:
- Immutable deployment artifact promoted across environments.
- Database and schema compatibility checks are backward-compatible before release.
- Rollback artifact and runbook must be prepared at release cut time.

## 17) Cost Guardrails (Free-Tier Aligned)

Guardrails:
- Bound live telemetry frequency per camera.
- Enforce max page size and query window for list endpoints.
- Monitor and alert on DynamoDB read/write consumption trends.
- Apply strict S3 lifecycle and log retention settings.

Monthly review:
- Compare actual usage vs free-tier assumptions and adjust polling and retention configs.

## 18) Requirement Traceability Matrix

Objective and stack requirement: edge inference stays local
- Planned module: ingest API only receives telemetry and confirmed violation metadata
- Verification: no raw video ingestion endpoints exist in public contract

Objective and stack requirement: persist only confirmed violations and evidence
- Planned module: worker lifecycle states and violation status policy
- Verification: default list query excludes rejected and non-confirmed enforcement records

Objective and stack requirement: ephemeral live telemetry with TTL
- Planned module: CameraLiveState table with expires_at field
- Verification: telemetry records age out automatically within configured window

Objective and stack requirement: resilient async processing
- Planned module: violation_ingest_queue plus DLQ and replay runbook
- Verification: ingest remains available during downstream slowdown

Objective and stack requirement: secure evidence storage and retrieval
- Planned module: S3 private bucket plus signed URL endpoint authorization checks
- Verification: direct public object access is denied and signed URL access is time-bound

Objective and stack requirement: free-tier-first AWS posture
- Planned module: cost guardrails, retention policy, and request shaping
- Verification: monthly cost review and quota drift checks remain within target envelope

