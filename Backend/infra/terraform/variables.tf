variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "local_mode" {
  type    = bool
  default = false
}

variable "local_account_id" {
  type    = string
  default = "000000000000"
}

variable "project_name" {
  type    = string
  default = "footwatch"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "lambda_timeout_seconds" {
  type    = number
  default = 20
}

variable "lambda_memory_mb" {
  type    = number
  default = 512
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "alarm_topic_arn" {
  type    = string
  default = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}
