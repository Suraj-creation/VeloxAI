terraform {
  required_version = ">= 1.6.0"
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

  access_key = var.local_mode ? "test" : null
  secret_key = var.local_mode ? "test" : null

  skip_credentials_validation = var.local_mode
  skip_requesting_account_id  = var.local_mode
  skip_metadata_api_check     = var.local_mode
  skip_region_validation      = var.local_mode
}
