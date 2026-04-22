data "aws_caller_identity" "current" {
  count = var.local_mode ? 0 : 1
}

data "aws_iam_policy_document" "evidence_bucket_tls_only" {
	statement {
		sid    = "DenyInsecureTransport"
		effect = "Deny"

		principals {
			type        = "*"
			identifiers = ["*"]
		}

		actions = ["s3:*"]
		resources = [
			aws_s3_bucket.evidence.arn,
			"${aws_s3_bucket.evidence.arn}/*",
		]

		condition {
			test     = "Bool"
			variable = "aws:SecureTransport"
			values   = ["false"]
		}
	}
}

locals {
  evidence_account_id = var.local_mode ? var.local_account_id : data.aws_caller_identity.current[0].account_id
}

resource "aws_s3_bucket" "evidence" {
	bucket        = "${local.name_prefix}-evidence-${local.evidence_account_id}"
	force_destroy = var.force_destroy_evidence_bucket
	tags          = local.common_tags
}

resource "aws_s3_bucket_ownership_controls" "evidence" {
	bucket = aws_s3_bucket.evidence.id

	rule {
		object_ownership = "BucketOwnerEnforced"
	}
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
		bucket_key_enabled = var.evidence_bucket_kms_key_arn != null

		apply_server_side_encryption_by_default {
			sse_algorithm     = var.evidence_bucket_kms_key_arn != null ? "aws:kms" : "AES256"
			kms_master_key_id = var.evidence_bucket_kms_key_arn
		}
	}
}

resource "aws_s3_bucket_policy" "evidence_tls_only" {
	bucket = aws_s3_bucket.evidence.id
	policy = data.aws_iam_policy_document.evidence_bucket_tls_only.json
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
