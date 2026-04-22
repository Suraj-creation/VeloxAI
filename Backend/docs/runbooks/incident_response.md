# Incident Response Runbook

1. Capture impacted endpoint and request_id samples.
2. Check CloudWatch logs and alarm state.
3. Verify SQS queue backlog and DLQ growth.
4. Apply mitigation (scale worker, rollback, or isolate endpoint).
5. Publish post-incident summary with timeline and action items.
