# Deploy Runbook

1. Run tests: `pytest -q`.
2. Validate OpenAPI contract snapshots.
3. Apply Terraform changes in staging.
4. Promote immutable artifact to production.
5. Verify health checks and queue depth alarms.
