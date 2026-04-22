# FootWatch Backend

Modular backend scaffold for Objective 3 enforcement ingestion and dashboard query APIs.

## Quick Start

1. Create a virtual environment.
2. Install dependencies.
3. Run ingest API, query API, and worker.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn services.ingest_api.app:app --reload --port 8000
.\.venv\Scripts\python.exe -m uvicorn services.query_api.app:app --reload --port 8001
.\.venv\Scripts\python.exe -m services.workers.process_violation_queue.handler
```

Set frontend API base URL to `http://localhost:8001` while testing dashboard reads.

## Terraform

### Local Dry-Run (No AWS Credentials)

Use local mode to test Terraform graph and plan output without connecting to AWS:

```powershell
terraform -chdir=infra/terraform init -input=false -backend=false
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform plan -input=false -refresh=false -var="local_mode=true"
```

This mode uses dummy credentials and a synthetic account ID for naming, so you can verify config logic safely on your machine.

### Real AWS Plan/Apply

For real infrastructure plans or apply, configure AWS credentials first (profile or environment variables), then use the S3 backend for shared state and locking.

Common environment variables:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN` (only for temporary STS credentials)
- `AWS_REGION` or `AWS_DEFAULT_REGION`

Recommended one-time bootstrap (state bucket + lock table):

```powershell
aws s3api create-bucket --bucket footwatch-tfstate-<account-id> --region ap-south-1 --create-bucket-configuration LocationConstraint=ap-south-1
aws s3api put-bucket-versioning --bucket footwatch-tfstate-<account-id> --versioning-configuration Status=Enabled
aws dynamodb create-table --table-name footwatch-terraform-locks --attribute-definitions AttributeName=LockID,AttributeType=S --key-schema AttributeName=LockID,KeyType=HASH --billing-mode PAY_PER_REQUEST --region ap-south-1
```

Then configure Terraform backend and variables:

```powershell
Copy-Item infra/terraform/backend.hcl.example infra/terraform/backend.hcl
Copy-Item infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
```

Set a strong ingest key through environment variable (preferred over storing plain text in tfvars):

```powershell
$env:TF_VAR_ingest_api_key = "<strong-secret-at-least-16-chars>"
```

Then run:

```powershell
terraform -chdir=infra/terraform init -input=false -reconfigure -backend-config=backend.hcl
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform plan -input=false -var-file=terraform.tfvars
terraform -chdir=infra/terraform apply -input=false -var-file=terraform.tfvars
```

This scaffold keeps edge inference local and ingests telemetry plus confirmed violation metadata only.
