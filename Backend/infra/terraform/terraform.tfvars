aws_region                   = "ap-south-1"
environment                  = "dev"
project_name                 = "footwatch"
allowed_account_ids          = ["769213333967"]
lambda_timeout_seconds       = 20
lambda_memory_mb             = 512
worker_timeout_seconds       = 60
worker_memory_mb             = 1024
queue_visibility_timeout_seconds = 180
queue_max_receive_count      = 5
log_retention_days           = 14

# Optional
alarm_topic_arn              = ""
evidence_bucket_kms_key_arn  = null
force_destroy_evidence_bucket = false

tags = {
  Owner = "footwatch-team"
}
