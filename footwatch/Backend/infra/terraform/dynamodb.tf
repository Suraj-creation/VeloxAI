locals {
	name_prefix = "${var.project_name}-${var.environment}"
	common_tags = merge(var.tags, {
		Project     = var.project_name
		Environment = var.environment
		ManagedBy   = "terraform"
	})
}

resource "aws_dynamodb_table" "camera_live_state" {
	name         = "${local.name_prefix}-camera-live-state"
	billing_mode = "PAY_PER_REQUEST"
	hash_key     = "camera_id"
	deletion_protection_enabled = var.environment == "prod"

	attribute {
		name = "camera_id"
		type = "S"
	}

	ttl {
		attribute_name = "ttl_epoch"
		enabled        = true
	}

	point_in_time_recovery {
		enabled = true
	}

	server_side_encryption {
		enabled = true
	}

	tags = local.common_tags
}

resource "aws_dynamodb_table" "violations" {
	name         = "${local.name_prefix}-violations"
	billing_mode = "PAY_PER_REQUEST"
	hash_key     = "violation_id"
	deletion_protection_enabled = var.environment == "prod"

	attribute {
		name = "violation_id"
		type = "S"
	}

	attribute {
		name = "camera_id"
		type = "S"
	}

	attribute {
		name = "timestamp"
		type = "S"
	}

	global_secondary_index {
		name            = "by_camera_timestamp"
		hash_key        = "camera_id"
		range_key       = "timestamp"
		projection_type = "ALL"
	}

	point_in_time_recovery {
		enabled = true
	}

	server_side_encryption {
		enabled = true
	}

	tags = local.common_tags
}

resource "aws_dynamodb_table" "idempotency_records" {
	name         = "${local.name_prefix}-idempotency-records"
	billing_mode = "PAY_PER_REQUEST"
	hash_key     = "idempotency_key"
	deletion_protection_enabled = var.environment == "prod"

	attribute {
		name = "idempotency_key"
		type = "S"
	}

	ttl {
		attribute_name = "expires_at"
		enabled        = true
	}

	point_in_time_recovery {
		enabled = true
	}

	server_side_encryption {
		enabled = true
	}

	tags = local.common_tags
}
