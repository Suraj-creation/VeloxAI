# FootWatch Free-Tier-Optimized Tech Stack (AWS)

## 1. Core Objective (Revalidated)

This stack is aligned to your exact project goal:

- robust realtime dashboard for operations
- functional backend APIs and storage
- edge processing stays local on camera node
- store only confirmed violations and evidence
- use only free or free-tier services for MVP

## 2. Service Decision Matrix (Based On Your Free-Tier List)

The table below maps each listed AWS service to whether it is required for FootWatch MVP.

| Service | Free Model | MVP Decision | Why |
| --- | --- | --- | --- |
| AWS Lambda | Always Free + 12-month quotas | Required | Core backend compute for ingest/query APIs |
| Amazon DynamoDB | Always Free | Required | Best low-cost metadata store for live + violations |
| Amazon S3 | 12-month Free Tier | Required | Evidence image storage |
| Amazon CloudFront | 12-month Free Tier | Required | Fast static dashboard delivery |
| Amazon CloudWatch | Limited free | Required | Logs and basic operational visibility |
| AWS IAM | Always free | Required | Access control and least privilege |
| AWS STS | Always free | Required | Temporary credentials for secure access patterns |
| Amazon SQS | 12-month Free Tier | Required | Queue to decouple violation processing |
| Amazon SNS | 12-month Free Tier | Optional | Alerting for critical violation events or failures |
| Amazon EC2 | 12-month Free Tier | Optional | Only if you need an always-on worker/control server |
| Amazon EBS | 12-month Free Tier | Optional | Needed only with EC2 for attached persistent disk |
| Amazon RDS | 12-month Free Tier | Not required in MVP | DynamoDB already satisfies current workload |

Note:

- API Gateway is still used for REST endpoints because it is the simplest managed API layer for this design.
- Free-tier quotas vary by account age, region, and AWS policy updates, so verify in your AWS Billing console.

## 3. Final MVP Architecture (Free-Tier First)

1. Edge device runs current detection/tracking/OCR pipeline.
2. Edge generates two payload types:
   - live telemetry (ephemeral)
   - confirmed violation events (persistent)
3. Edge uploads evidence images to S3 using presigned URLs.
4. Edge sends telemetry and violation metadata to API Gateway.
5. Lambda handles validation and routing:
   - telemetry -> DynamoDB CameraLiveState with TTL
   - violation metadata -> SQS queue
6. Violation worker Lambda consumes SQS and writes final records to DynamoDB Violations.
7. Frontend dashboard is hosted on S3 + CloudFront and polls REST APIs every few seconds.
8. Optional: SNS sends operator alerts for key events.

This architecture provides robust behavior without premium services like AppSync/OpenSearch/Glue.

## 4. Detailed Stack

## 4.1 Edge Layer

- Runtime: Python 3.11
- CV/ML: ultralytics, opencv-python, paddleocr
- Reliability:
  - local disk spool for offline recovery
  - retry with exponential backoff
  - idempotent violation_id per event

## 4.2 Backend Layer

- API Gateway HTTP API
- Lambda functions:
  - post_telemetry
  - post_violation_metadata
  - process_violation_from_queue
  - get_live_cameras
  - list_violations
  - get_violation_details
  - get_presigned_evidence_url
- SQS:
  - violation_ingest_queue
  - violation_dlq
- SNS (optional):
  - ops_alert_topic

## 4.3 Data Layer

- DynamoDB table: CameraLiveState
  - PK: camera_id
  - TTL: expires_at (120-300 seconds)
- DynamoDB table: Violations
  - PK: violation_id
  - GSI1: camera_id + event_ts
  - GSI2: plate_number + event_ts
- S3 bucket: footwatch-evidence
  - prefixes:
    - evidence/full_frame/
    - evidence/plate_raw/
    - evidence/plate_enhanced/
    - evidence/thumbnail/

## 4.4 Frontend Layer

- Framework: React + TypeScript (Vite)
- Data fetching: TanStack Query
- Charts: Recharts
- Hosting: S3 static site + CloudFront
- Realtime method: short polling
  - GET /v1/live/cameras every 2-5 seconds
  - GET /v1/violations/recent every 5-10 seconds

## 5. Why EC2/EBS/RDS Are Not Core In MVP

- EC2/EBS are optional only when you need a permanent custom server.
- RDS is unnecessary for current violation workload and would add cost/ops overhead.
- DynamoDB + Lambda + S3 already meets your current scale and feature requirements.

## 6. API Surface (MVP)

- POST /v1/telemetry
- POST /v1/violations
- POST /v1/violations/{id}/evidence-complete
- GET /v1/live/cameras
- GET /v1/violations?from=&to=&camera_id=&plate=&class=
- GET /v1/violations/{id}
- GET /v1/violations/{id}/evidence-url?type=full_frame

## 7. Data Policy (Objective 3 Compliant)

- persist only confirmed violations and evidence
- keep live telemetry ephemeral with DynamoDB TTL
- do not store non-violation detections as permanent records

## 8. Cost Guardrails

- telemetry publish interval: 2-3 seconds per camera
- dashboard polling interval: 3-5 seconds
- evidence image resize before upload
- S3 lifecycle rules for old evidence
- CloudWatch log retention set to low duration (for example 7-14 days)
- SQS + DLQ for failure isolation instead of expensive always-on compute

## 9. Services Removed From MVP (Premium Or Non-Essential)

- AWS AppSync
- AWS OpenSearch
- AWS Glue
- Amazon Athena
- AWS GuardDuty
- AWS X-Ray
- AWS IoT Greengrass
- customer-managed KMS keys

These can be added later only after traffic and budget justify them.

## 10. Delivery Phases

## Phase 1: Free-Tier MVP Backbone

1. Create DynamoDB tables, S3 bucket, and SQS queue
2. Deploy API Gateway + Lambdas
3. Wire edge app to S3 presigned upload + API posts
4. Build and deploy React dashboard on S3 + CloudFront

## Phase 2: Reliability And Security

1. Add IAM role hardening and STS-based access flows
2. Add SNS alerts and DLQ replay tooling
3. Add CloudWatch alarms for error rate and latency

## Phase 3: Optional Expansion

1. Add EC2/EBS worker only if needed
2. Add RDS only if relational reporting becomes mandatory
3. Add premium analytics/search stack later

## 11. Final Recommendation

Your best stack under free-tier constraints is:

- Edge inference local (existing Python pipeline)
- API Gateway + Lambda for backend APIs
- DynamoDB for live and violation metadata
- S3 for evidence storage
- SQS for resilient asynchronous processing
- CloudFront + S3 for frontend hosting
- CloudWatch + IAM + STS for operations and security baseline

This gives a complete, robust, realtime-capable FootWatch platform with minimal cost and no premium-first dependencies.
