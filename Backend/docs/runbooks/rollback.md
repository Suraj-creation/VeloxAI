# Rollback Runbook

1. Stop new deployment traffic routing.
2. Promote previous stable artifact.
3. Confirm ingest and query endpoint health.
4. Verify data integrity (latest violation_id sequence continuity).
5. Document incident and root cause.
