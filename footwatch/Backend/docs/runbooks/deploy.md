# Deploy Runbook

1. Run backend tests and contract checks.
2. Prepare Terraform inputs: update `infra/terraform/terraform.tfvars` for target env and export `TF_VAR_ingest_api_key`.
3. Initialize Terraform with remote backend config: `terraform -chdir=infra/terraform init -input=false -reconfigure -backend-config=backend.hcl`.
4. Run `terraform -chdir=infra/terraform validate`.
5. Run staged plan: `terraform -chdir=infra/terraform plan -input=false -var-file=terraform.tfvars` and review diffs.
6. Apply in staging: `terraform -chdir=infra/terraform apply -input=false -var-file=terraform.tfvars`.
7. Smoke test API routes (`/ingest/*`, `/query/*`) and verify Lambda, SQS, and DynamoDB metrics.
8. Repeat plan/apply for production with production backend key and tfvars.
9. Verify CloudWatch alarms (queue backlog and DLQ), API access logs, and error rates.
