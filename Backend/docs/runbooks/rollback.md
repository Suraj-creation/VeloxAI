# Rollback Runbook

1. Stop new deployment traffic routing.
2. Re-run Terraform plan against last known-good revision.
3. Apply rollback (`terraform apply`) for infrastructure-level regression, or redeploy previous function artifacts.
4. Confirm ingest and query endpoint health.
5. Verify queue backlog/DLQ behavior and replay messages if needed.
6. Verify data integrity (latest violation_id sequence continuity).
7. Document incident and root cause.
