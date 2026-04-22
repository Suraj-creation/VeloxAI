resource "aws_cloudwatch_log_group" "ingest_api" {
	name              = "/aws/lambda/${local.name_prefix}-ingest-api"
	retention_in_days = var.log_retention_days
	tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "query_api" {
	name              = "/aws/lambda/${local.name_prefix}-query-api"
	retention_in_days = var.log_retention_days
	tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "worker" {
	name              = "/aws/lambda/${local.name_prefix}-worker"
	retention_in_days = var.log_retention_days
	tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "http_api_access" {
	name              = "/aws/apigateway/${local.name_prefix}-http-api"
	retention_in_days = var.log_retention_days
	tags              = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "queue_visible_messages_high" {
	alarm_name          = "${local.name_prefix}-queue-visible-messages-high"
	comparison_operator = "GreaterThanThreshold"
	evaluation_periods  = 2
	metric_name         = "ApproximateNumberOfMessagesVisible"
	namespace           = "AWS/SQS"
	period              = 60
	statistic           = "Average"
	threshold           = 25
	alarm_description   = "Violation queue backlog is high"
	treat_missing_data  = "notBreaching"

	dimensions = {
		QueueName = aws_sqs_queue.violation_ingest_queue.name
	}

	alarm_actions = var.alarm_topic_arn == "" ? [] : [var.alarm_topic_arn]
	ok_actions    = var.alarm_topic_arn == "" ? [] : [var.alarm_topic_arn]
}

resource "aws_cloudwatch_metric_alarm" "dlq_has_messages" {
	alarm_name          = "${local.name_prefix}-dlq-has-messages"
	comparison_operator = "GreaterThanThreshold"
	evaluation_periods  = 1
	metric_name         = "ApproximateNumberOfMessagesVisible"
	namespace           = "AWS/SQS"
	period              = 60
	statistic           = "Average"
	threshold           = 0
	alarm_description   = "DLQ contains failed messages"
	treat_missing_data  = "notBreaching"

	dimensions = {
		QueueName = aws_sqs_queue.violation_dlq.name
	}

	alarm_actions = var.alarm_topic_arn == "" ? [] : [var.alarm_topic_arn]
	ok_actions    = var.alarm_topic_arn == "" ? [] : [var.alarm_topic_arn]
}
