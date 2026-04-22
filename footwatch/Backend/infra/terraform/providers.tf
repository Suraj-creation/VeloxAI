terraform {
  required_version = ">= 1.6.0"

  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.5"
    }
  }
}

provider "aws" {
  region = var.aws_region

  allowed_account_ids = var.allowed_account_ids

  access_key = var.local_mode ? "test" : null
  secret_key = var.local_mode ? "test" : null

  skip_credentials_validation = var.local_mode
  skip_requesting_account_id  = var.local_mode
  skip_metadata_api_check     = var.local_mode
  skip_region_validation      = var.local_mode

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
