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
terraform -chdir=infra/terraform init -input=false
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform plan -input=false -refresh=false -var="local_mode=true"
```

This mode uses dummy credentials and a synthetic account ID for naming, so you can verify config logic safely on your machine.

### Real AWS Plan/Apply

For real infrastructure plans or apply, configure AWS credentials first (profile or environment variables).

Common environment variables:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN` (only for temporary STS credentials)
- `AWS_REGION` or `AWS_DEFAULT_REGION`

Then run:

```powershell
terraform -chdir=infra/terraform plan -input=false
```

This scaffold keeps edge inference local and ingests telemetry plus confirmed violation metadata only.
