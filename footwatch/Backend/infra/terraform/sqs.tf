resource "aws_sqs_queue" "violation_dlq" {
	name                      = "${local.name_prefix}-violation-dlq"
	message_retention_seconds = 1209600
	sqs_managed_sse_enabled   = true
	tags                      = local.common_tags
}

resource "aws_sqs_queue" "violation_ingest_queue" {
	name                       = "${local.name_prefix}-violation-ingest-queue"
	visibility_timeout_seconds = var.queue_visibility_timeout_seconds
	message_retention_seconds  = 345600
	receive_wait_time_seconds  = 20
	sqs_managed_sse_enabled    = true

	redrive_policy = jsonencode({
		deadLetterTargetArn = aws_sqs_queue.violation_dlq.arn
		maxReceiveCount     = var.queue_max_receive_count
	})

	tags = local.common_tags
}

resource "aws_sqs_queue_redrive_allow_policy" "violation_dlq" {
	queue_url = aws_sqs_queue.violation_dlq.id

	redrive_allow_policy = jsonencode({
		redrivePermission = "byQueue"
		sourceQueueArns   = [aws_sqs_queue.violation_ingest_queue.arn]
	})
}
