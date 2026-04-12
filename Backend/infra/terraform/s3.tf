data "aws_caller_identity" "current" {
  count = var.local_mode ? 0 : 1
}

locals {
  evidence_account_id = var.local_mode ? var.local_account_id : data.aws_caller_identity.current[0].account_id
}

resource "aws_s3_bucket" "evidence" {
	bucket = "${local.name_prefix}-evidence-${local.evidence_account_id}"
	tags   = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "evidence" {
	bucket                  = aws_s3_bucket.evidence.id
	block_public_acls       = true
	ignore_public_acls      = true
	block_public_policy     = true
	restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "evidence" {
	bucket = aws_s3_bucket.evidence.id

	versioning_configuration {
		status = "Enabled"
	}
}

resource "aws_s3_bucket_server_side_encryption_configuration" "evidence" {
	bucket = aws_s3_bucket.evidence.id

	rule {
		apply_server_side_encryption_by_default {
			sse_algorithm = "AES256"
		}
	}
}

resource "aws_s3_bucket_lifecycle_configuration" "evidence" {
	bucket = aws_s3_bucket.evidence.id

	rule {
		id     = "expire-old-evidence"
		status = "Enabled"

		filter {}

		expiration {
			days = 90
		}

		noncurrent_version_expiration {
			noncurrent_days = 30
		}
	}
}
