resource "aws_s3_bucket" "upload_areas_bucket" {
  bucket = "${local.bucket_name}"
  acl = "private"
  force_destroy = "false"
  acceleration_status = "Enabled"
  tags = {
    Project = "hca"
  }

}

resource "aws_iam_policy" "upload_areas_submitter_access" {
  name = "dcp-upload-areas-submitter-access-${var.deployment_stage}"
  // Note that this policy creates very broad access, to all upload areas in the bucket.
  // It will be narrowed down to a single upload area during the AssumeRole process.
  policy = <<POLICY
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:PutObjectTagging"
            ],
            "Resource": [
                "arn:aws:s3:::${aws_s3_bucket.upload_areas_bucket.bucket}/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::${aws_s3_bucket.upload_areas_bucket.bucket}"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:Get*",
                "s3:List*"
            ],
            "Resource": [
                "${var.staging_bucket_arn}/*",
                "${var.staging_bucket_arn}",
                "arn:aws:s3:::org-humancellatlas-dcp-test-data",
                "arn:aws:s3:::org-humancellatlas-dcp-test-data/*"
            ]
        }
    ]
}
POLICY
}

locals {
  # The ARN of the principal of the running API Lambda
  api_lambda_principal_arn = "arn:aws:sts::${local.account_id}:assumed-role/${aws_iam_role.upload_api_lambda.name}/${aws_lambda_function.upload_api_lambda.function_name}"
}

resource "aws_iam_role" "upload_submitter" {
  name = "dcp-upload-submitter-${var.deployment_stage}"
  max_session_duration = 3600,
  assume_role_policy = <<POLICY
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "",
            "Effect": "Allow",
            "Principal": {
                "AWS": "${local.api_lambda_principal_arn}"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
POLICY
}

resource "aws_iam_role_policy_attachment" "upload_submitter" {
  role = "${aws_iam_role.upload_submitter.name}"
  policy_arn = "${aws_iam_policy.upload_areas_submitter_access.arn}"
}

resource "aws_s3_bucket" "lambda_deployments" {
  bucket = "${var.bucket_name_prefix}lambda-deployment-${var.deployment_stage}"
  acl = "private"
  force_destroy = "false"
  acceleration_status = "Enabled"
  tags = {
    Project = "hca"
  }
}
