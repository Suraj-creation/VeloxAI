data "aws_iam_policy_document" "lambda_assume_role" {
	statement {
		actions = ["sts:AssumeRole"]

		principals {
			type        = "Service"
			identifiers = ["lambda.amazonaws.com"]
		}
	}
}

resource "aws_iam_role" "lambda_exec" {
	name               = "${local.name_prefix}-lambda-exec"
	assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
	tags               = local.common_tags
}

data "aws_iam_policy_document" "lambda_access" {
	statement {
		sid = "DynamoDbAccess"
		actions = [
			"dynamodb:GetItem",
			"dynamodb:PutItem",
			"dynamodb:UpdateItem",
			"dynamodb:Query",
			"dynamodb:Scan",
		]
		resources = [
			aws_dynamodb_table.camera_live_state.arn,
			aws_dynamodb_table.violations.arn,
			aws_dynamodb_table.idempotency_records.arn,
			"${aws_dynamodb_table.violations.arn}/index/*",
		]
	}

	statement {
		sid = "S3EvidenceAccess"
		actions = [
			"s3:GetObject",
			"s3:PutObject",
			"s3:ListBucket",
		]
		resources = [
			aws_s3_bucket.evidence.arn,
			"${aws_s3_bucket.evidence.arn}/*",
		]
	}

	statement {
		sid = "QueueAccess"
		actions = [
			"sqs:SendMessage",
			"sqs:ReceiveMessage",
			"sqs:DeleteMessage",
			"sqs:ChangeMessageVisibility",
			"sqs:GetQueueAttributes",
		]
		resources = [
			aws_sqs_queue.violation_ingest_queue.arn,
			aws_sqs_queue.violation_dlq.arn,
		]
	}

	statement {
		sid = "XRayAccess"
		actions = [
			"xray:PutTraceSegments",
			"xray:PutTelemetryRecords",
		]
		resources = ["*"]
	}

	dynamic "statement" {
		for_each = var.evidence_bucket_kms_key_arn == null ? [] : [var.evidence_bucket_kms_key_arn]
		content {
			sid = "KmsForEvidenceBucket"
			actions = [
				"kms:Decrypt",
				"kms:Encrypt",
				"kms:GenerateDataKey",
			]
			resources = [statement.value]
		}
	}

	statement {
		sid = "CloudWatchLogs"
		actions = [
			"logs:CreateLogStream",
			"logs:PutLogEvents",
		]
		resources = [
			"${aws_cloudwatch_log_group.ingest_api.arn}:*",
			"${aws_cloudwatch_log_group.query_api.arn}:*",
			"${aws_cloudwatch_log_group.worker.arn}:*",
		]
	}
}

resource "aws_iam_policy" "lambda_access" {
	name   = "${local.name_prefix}-lambda-access"
	policy = data.aws_iam_policy_document.lambda_access.json
}

resource "aws_iam_role_policy_attachment" "lambda_access" {
	role       = aws_iam_role.lambda_exec.name
	policy_arn = aws_iam_policy.lambda_access.arn
}
