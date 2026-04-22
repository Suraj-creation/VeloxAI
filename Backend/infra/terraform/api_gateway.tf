resource "aws_apigatewayv2_api" "http_api" {
	name          = "${local.name_prefix}-http-api"
	protocol_type = "HTTP"
	tags          = local.common_tags
}

resource "aws_apigatewayv2_integration" "ingest_api" {
	api_id                 = aws_apigatewayv2_api.http_api.id
	integration_type       = "AWS_PROXY"
	integration_uri        = aws_lambda_function.ingest_api.invoke_arn
	payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "query_api" {
	api_id                 = aws_apigatewayv2_api.http_api.id
	integration_type       = "AWS_PROXY"
	integration_uri        = aws_lambda_function.query_api.invoke_arn
	payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "ingest_proxy" {
	api_id    = aws_apigatewayv2_api.http_api.id
	route_key = "ANY /ingest/{proxy+}"
	target    = "integrations/${aws_apigatewayv2_integration.ingest_api.id}"
}

resource "aws_apigatewayv2_route" "query_proxy" {
	api_id    = aws_apigatewayv2_api.http_api.id
	route_key = "ANY /query/{proxy+}"
	target    = "integrations/${aws_apigatewayv2_integration.query_api.id}"
}

resource "aws_apigatewayv2_stage" "default" {
	api_id      = aws_apigatewayv2_api.http_api.id
	name        = "$default"
	auto_deploy = true

	default_route_settings {
		detailed_metrics_enabled = true
		throttling_burst_limit   = var.api_throttle_burst_limit
		throttling_rate_limit    = var.api_throttle_rate_limit
	}

	access_log_settings {
		destination_arn = aws_cloudwatch_log_group.http_api_access.arn
		format = jsonencode({
			requestId        = "$context.requestId"
			ip               = "$context.identity.sourceIp"
			requestTime      = "$context.requestTime"
			httpMethod       = "$context.httpMethod"
			routeKey         = "$context.routeKey"
			status           = "$context.status"
			protocol         = "$context.protocol"
			responseLength   = "$context.responseLength"
			integrationError = "$context.integrationErrorMessage"
		})
	}

	tags        = local.common_tags
}

resource "aws_lambda_permission" "apigw_invoke_ingest" {
	statement_id  = "AllowExecutionFromApiGatewayIngest"
	action        = "lambda:InvokeFunction"
	function_name = aws_lambda_function.ingest_api.function_name
	principal     = "apigateway.amazonaws.com"
	source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "apigw_invoke_query" {
	statement_id  = "AllowExecutionFromApiGatewayQuery"
	action        = "lambda:InvokeFunction"
	function_name = aws_lambda_function.query_api.function_name
	principal     = "apigateway.amazonaws.com"
	source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}
