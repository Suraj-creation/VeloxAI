check "ingest_api_key_required_for_aws_deploy" {
  assert {
    condition     = var.local_mode || (var.ingest_api_key != null && trimspace(var.ingest_api_key) != "")
    error_message = "Set ingest_api_key when local_mode=false (real AWS deployment)."
  }
}

check "queue_visibility_covers_worker_runtime" {
  assert {
    condition     = var.queue_visibility_timeout_seconds >= (var.worker_timeout_seconds * 2)
    error_message = "queue_visibility_timeout_seconds should be at least 2x worker_timeout_seconds to reduce duplicate deliveries."
  }
}
