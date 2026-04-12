resource "aws_sqs_queue" "violation_dlq" {
	name                      = "${local.name_prefix}-violation-dlq"
	message_retention_seconds = 1209600
	tags                      = local.common_tags
}

resource "aws_sqs_queue" "violation_ingest_queue" {
	name                       = "${local.name_prefix}-violation-ingest-queue"
	visibility_timeout_seconds = 60
	message_retention_seconds  = 345600

	redrive_policy = jsonencode({
		deadLetterTargetArn = aws_sqs_queue.violation_dlq.arn
		maxReceiveCount     = 5
	})

	tags = local.common_tags
}
