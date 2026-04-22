variable "aws_region" {
  type    = string
  default = "ap-south-1"

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]$", var.aws_region))
    error_message = "aws_region must look like ap-south-1."
  }
}

variable "local_mode" {
  type    = bool
  default = false
}

variable "local_account_id" {
  type    = string
  default = "000000000000"

  validation {
    condition     = can(regex("^\\d{12}$", var.local_account_id))
    error_message = "local_account_id must be a 12-digit account id string."
  }
}

variable "allowed_account_ids" {
  type     = list(string)
  default  = null
  nullable = true

  validation {
    condition     = var.allowed_account_ids == null || alltrue([for id in var.allowed_account_ids : can(regex("^\\d{12}$", id))])
    error_message = "allowed_account_ids entries must be 12-digit AWS account ids."
  }
}

variable "project_name" {
  type    = string
  default = "footwatch"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,30}$", var.project_name))
    error_message = "project_name must be 3-30 characters and contain only lowercase letters, numbers, or dashes."
  }
}

variable "environment" {
  type    = string
  default = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "lambda_timeout_seconds" {
  type    = number
  default = 20

  validation {
    condition     = var.lambda_timeout_seconds >= 3 && var.lambda_timeout_seconds <= 900
    error_message = "lambda_timeout_seconds must be between 3 and 900."
  }
}

variable "lambda_memory_mb" {
  type    = number
  default = 512

  validation {
    condition     = var.lambda_memory_mb >= 128 && var.lambda_memory_mb <= 10240 && var.lambda_memory_mb % 64 == 0
    error_message = "lambda_memory_mb must be between 128 and 10240, in 64 MB increments."
  }
}

variable "worker_timeout_seconds" {
  type    = number
  default = 60

  validation {
    condition     = var.worker_timeout_seconds >= 3 && var.worker_timeout_seconds <= 900
    error_message = "worker_timeout_seconds must be between 3 and 900."
  }
}

variable "worker_memory_mb" {
  type    = number
  default = 1024

  validation {
    condition     = var.worker_memory_mb >= 128 && var.worker_memory_mb <= 10240 && var.worker_memory_mb % 64 == 0
    error_message = "worker_memory_mb must be between 128 and 10240, in 64 MB increments."
  }
}

variable "queue_visibility_timeout_seconds" {
  type    = number
  default = 180

  validation {
    condition     = var.queue_visibility_timeout_seconds >= 30 && var.queue_visibility_timeout_seconds <= 43200
    error_message = "queue_visibility_timeout_seconds must be between 30 and 43200."
  }
}

variable "queue_max_receive_count" {
  type    = number
  default = 5

  validation {
    condition     = var.queue_max_receive_count >= 1 && var.queue_max_receive_count <= 1000
    error_message = "queue_max_receive_count must be between 1 and 1000."
  }
}

variable "log_retention_days" {
  type    = number
  default = 14

  validation {
    condition     = var.log_retention_days >= 1
    error_message = "log_retention_days must be at least 1 day."
  }
}

variable "alarm_topic_arn" {
  type    = string
  default = ""

  validation {
    condition     = var.alarm_topic_arn == "" || can(regex("^arn:aws[a-z-]*:sns:[a-z0-9-]+:\\d{12}:[A-Za-z0-9-_]{1,256}$", var.alarm_topic_arn))
    error_message = "alarm_topic_arn must be empty or a valid SNS topic ARN."
  }
}

variable "ingest_api_key" {
  type      = string
  default   = null
  nullable  = true
  sensitive = true

  validation {
    condition     = var.ingest_api_key == null || length(var.ingest_api_key) >= 16
    error_message = "ingest_api_key must be at least 16 characters when set."
  }
}

variable "force_destroy_evidence_bucket" {
  type    = bool
  default = false
}

variable "evidence_bucket_kms_key_arn" {
  type     = string
  default  = null
  nullable = true
}

variable "api_throttle_burst_limit" {
  type    = number
  default = 200

  validation {
    condition     = var.api_throttle_burst_limit > 0
    error_message = "api_throttle_burst_limit must be greater than 0."
  }
}

variable "api_throttle_rate_limit" {
  type    = number
  default = 100

  validation {
    condition     = var.api_throttle_rate_limit > 0
    error_message = "api_throttle_rate_limit must be greater than 0."
  }
}

variable "tags" {
  type    = map(string)
  default = {}
}
