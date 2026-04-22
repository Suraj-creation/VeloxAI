output "region" {
  value = var.aws_region
}

output "http_api_url" {
  value = aws_apigatewayv2_api.http_api.api_endpoint
}

output "ingest_prefix" {
  value = "${aws_apigatewayv2_api.http_api.api_endpoint}/ingest"
}

output "query_prefix" {
  value = "${aws_apigatewayv2_api.http_api.api_endpoint}/query"
}

output "evidence_bucket_name" {
  value = aws_s3_bucket.evidence.id
}

output "violation_queue_url" {
  value = aws_sqs_queue.violation_ingest_queue.url
}

output "violations_table_name" {
  value = aws_dynamodb_table.violations.name
}
