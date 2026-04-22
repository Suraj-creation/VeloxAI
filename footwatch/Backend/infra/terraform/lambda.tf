data "archive_file" "backend_bundle" {
	type        = "zip"
	source_dir  = "${path.module}/../.."
	output_path = "${path.module}/build/backend_bundle.zip"
	excludes = [
		".git",
		".local",
		".pytest_cache",
		".venv",
		"infra/terraform/backend.hcl",
		"infra/terraform/terraform.tfvars",
		"infra/terraform/tfplan*",
		"infra/terraform/plan*.txt",
		"infra/terraform/.terraform",
		"infra/terraform/build",
		"**/__pycache__/**",
		"**/*.pyc",
	]
}

locals {
	effective_ingest_api_key = var.local_mode ? "dev-local-ingest-key" : var.ingest_api_key
}

resource "aws_lambda_function" "ingest_api" {
	function_name    = "${local.name_prefix}-ingest-api"
	role             = aws_iam_role.lambda_exec.arn
	runtime          = "python3.11"
	handler          = "services.ingest_api.lambda_handler.handler"
	filename         = data.archive_file.backend_bundle.output_path
	source_code_hash = data.archive_file.backend_bundle.output_base64sha256
	timeout          = var.lambda_timeout_seconds
	memory_size      = var.lambda_memory_mb

	tracing_config {
		mode = "Active"
	}

	environment {
		variables = {
			FW_ENV                   = var.environment
			FW_REGION                = var.aws_region
			FW_CAMERA_STATE_TABLE    = aws_dynamodb_table.camera_live_state.name
			FW_VIOLATIONS_TABLE      = aws_dynamodb_table.violations.name
			FW_IDEMPOTENCY_TABLE     = aws_dynamodb_table.idempotency_records.name
			FW_VIOLATION_QUEUE_URL   = aws_sqs_queue.violation_ingest_queue.url
			FW_EVIDENCE_BUCKET       = aws_s3_bucket.evidence.id
			FW_INGEST_API_KEY        = local.effective_ingest_api_key
		}
	}

	tags = local.common_tags

	depends_on = [aws_cloudwatch_log_group.ingest_api]
}

resource "aws_lambda_function" "query_api" {
	function_name    = "${local.name_prefix}-query-api"
	role             = aws_iam_role.lambda_exec.arn
	runtime          = "python3.11"
	handler          = "services.query_api.lambda_handler.handler"
	filename         = data.archive_file.backend_bundle.output_path
	source_code_hash = data.archive_file.backend_bundle.output_base64sha256
	timeout          = var.lambda_timeout_seconds
	memory_size      = var.lambda_memory_mb

	tracing_config {
		mode = "Active"
	}

	environment {
		variables = {
			FW_ENV                   = var.environment
			FW_REGION                = var.aws_region
			FW_CAMERA_STATE_TABLE    = aws_dynamodb_table.camera_live_state.name
			FW_VIOLATIONS_TABLE      = aws_dynamodb_table.violations.name
			FW_IDEMPOTENCY_TABLE     = aws_dynamodb_table.idempotency_records.name
			FW_VIOLATION_QUEUE_URL   = aws_sqs_queue.violation_ingest_queue.url
			FW_EVIDENCE_BUCKET       = aws_s3_bucket.evidence.id
			FW_INGEST_API_KEY        = local.effective_ingest_api_key
		}
	}

	tags = local.common_tags

	depends_on = [aws_cloudwatch_log_group.query_api]
}

resource "aws_lambda_function" "worker" {
	function_name    = "${local.name_prefix}-worker"
	role             = aws_iam_role.lambda_exec.arn
	runtime          = "python3.11"
	handler          = "services.workers.process_violation_queue.lambda_handler.handler"
	filename         = data.archive_file.backend_bundle.output_path
	source_code_hash = data.archive_file.backend_bundle.output_base64sha256
	timeout          = var.worker_timeout_seconds
	memory_size      = var.worker_memory_mb

	tracing_config {
		mode = "Active"
	}

	environment {
		variables = {
			FW_ENV                   = var.environment
			FW_REGION                = var.aws_region
			FW_CAMERA_STATE_TABLE    = aws_dynamodb_table.camera_live_state.name
			FW_VIOLATIONS_TABLE      = aws_dynamodb_table.violations.name
			FW_IDEMPOTENCY_TABLE     = aws_dynamodb_table.idempotency_records.name
			FW_VIOLATION_QUEUE_URL   = aws_sqs_queue.violation_ingest_queue.url
			FW_EVIDENCE_BUCKET       = aws_s3_bucket.evidence.id
			FW_INGEST_API_KEY        = local.effective_ingest_api_key
		}
	}

	tags = local.common_tags

	depends_on = [aws_cloudwatch_log_group.worker]
}

resource "aws_lambda_event_source_mapping" "worker_queue" {
	event_source_arn = aws_sqs_queue.violation_ingest_queue.arn
	function_name    = aws_lambda_function.worker.arn
	batch_size       = 10
	enabled          = true
}
