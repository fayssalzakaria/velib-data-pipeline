terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region"   { default = "eu-north-1" }
variable "project_name" { default = "velib-pipeline" }
variable "environment"  { default = "prod" }
variable "alert_email"  { description = "Email pour les alertes SNS" }
variable "db_password"  {
  description = "Mot de passe Aurora"
  sensitive   = true
}
variable "gemini_api_key" {
  description = "Clé API Gemini"
  sensitive   = true
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
# S3
resource "aws_s3_bucket" "velib_data" {
  bucket = "${local.name_prefix}-data"
  tags   = local.common_tags
}

resource "aws_s3_bucket_versioning" "velib_data" {
  bucket = aws_s3_bucket.velib_data.id
  versioning_configuration { status = "Enabled" }
}

# IAM Role Lambda
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name_prefix}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy" "lambda" {
  name = "${local.name_prefix}-lambda-policy"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:CopyObject"]
        Resource = [
          aws_s3_bucket.velib_data.arn,
          "${aws_s3_bucket.velib_data.arn}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = aws_sns_topic.pipeline_alerts.arn
      }
    ]
  })
}

# Lambda Pipeline
data "archive_file" "pipeline_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../lambdas/pipeline"
  output_path = "${path.module}/build/pipeline.zip"
}
# Build du layer via Docker
resource "null_resource" "build_layer" {
  triggers = {
    always = timestamp()
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = "${path.module}/build_layer.sh"
  }
}

# Upload le layer sur S3
resource "aws_s3_object" "layer_zip" {
  bucket     = aws_s3_bucket.velib_data.bucket
  key        = "builds/layer.zip"
  source     = "${path.module}/build/layer.zip"
  depends_on = [null_resource.build_layer]
}

# Crée le Lambda Layer depuis S3

resource "aws_lambda_layer_version" "dependencies" {
  layer_name          = "${local.name_prefix}-dependencies"
  s3_bucket           = aws_s3_bucket.velib_data.bucket
  s3_key              = aws_s3_object.layer_zip.key
  compatible_runtimes = ["python3.12"]
  depends_on          = [aws_s3_object.layer_zip]
}
resource "aws_lambda_function" "pipeline" {
  function_name    = "${local.name_prefix}-pipeline"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 300
  memory_size      = 1024
  filename         = data.archive_file.pipeline_zip.output_path
  source_code_hash = data.archive_file.pipeline_zip.output_base64sha256
  layers = [aws_lambda_layer_version.dependencies.arn]
  environment {
    variables = {
      S3_BUCKET           = aws_s3_bucket.velib_data.bucket
      SNS_ALERT_TOPIC_ARN = aws_sns_topic.pipeline_alerts.arn
      AWS_REGION_NAME     = var.aws_region
      GEMINI_API_KEY      = var.gemini_api_key
      POSTGRES_URL = "postgresql://velib_app:${var.db_password}@${aws_rds_cluster.aurora.endpoint}/velib"
    }
  }
  tags = local.common_tags
}

# Lambda API
data "archive_file" "api_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../lambdas/api"
  output_path = "${path.module}/build/api.zip"
}

resource "aws_lambda_function" "api" {
  function_name    = "${local.name_prefix}-api"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 256
  filename         = data.archive_file.api_zip.output_path
  source_code_hash = data.archive_file.api_zip.output_base64sha256

  environment {
    variables = {
      S3_BUCKET = aws_s3_bucket.velib_data.bucket
    }
  }
  tags = local.common_tags
}
# API Gateway
resource "aws_apigatewayv2_api" "main" {
  name          = "${local.name_prefix}-api"
  protocol_type = "HTTP"
  tags          = local.common_tags
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "api_lambda" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "report" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /download/report"
  target    = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
}

resource "aws_apigatewayv2_route" "csv" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /download/csv"
  target    = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
}

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

# EventBridge Scheduler (remplace Airflow)
resource "aws_iam_role" "scheduler" {
  name = "${local.name_prefix}-scheduler-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "scheduler" {
  name = "invoke-lambda"
  role = aws_iam_role.scheduler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.pipeline.arn
    }]
  })
}

resource "aws_scheduler_schedule" "hourly" {
  name       = "${local.name_prefix}-hourly"
  group_name = "default"

  flexible_time_window { mode = "OFF" }
  schedule_expression = "cron(0 * * * ? *)"

  target {
    arn      = aws_lambda_function.pipeline.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode({ source = "eventbridge-scheduler" })

    retry_policy {
      maximum_retry_attempts       = 2
      maximum_event_age_in_seconds = 3600
    }
  }
}

# SNS Alertes
resource "aws_sns_topic" "pipeline_alerts" {
  name = "${local.name_prefix}-alerts"
  tags = local.common_tags
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.pipeline_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# CloudWatch Alarm
resource "aws_cloudwatch_metric_alarm" "pipeline_errors" {
  alarm_name          = "${local.name_prefix}-errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 3600
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Pipeline Velib en echec"
  alarm_actions       = [aws_sns_topic.pipeline_alerts.arn]

  dimensions = {
    FunctionName = aws_lambda_function.pipeline.function_name
  }
}
# VPC pour Aurora
data "aws_availability_zones" "available" { state = "available" }
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = merge(local.common_tags, { Name = "${local.name_prefix}-vpc" })
}

resource "aws_subnet" "public" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  tags = merge(local.common_tags, { Name = "${local.name_prefix}-subnet-${count.index}" })
}
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = merge(local.common_tags, { Name = "${local.name_prefix}-igw" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = merge(local.common_tags, { Name = "${local.name_prefix}-rt" })
}
resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Security Group Aurora — port 5432 ouvert
resource "aws_security_group" "aurora" {
  name   = "${local.name_prefix}-aurora-sg"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.common_tags
}

# Aurora Serverless v2
resource "aws_db_subnet_group" "aurora" {
  name       = "${local.name_prefix}-subnet-group"
  subnet_ids = aws_subnet.public[*].id
  tags       = local.common_tags
}

resource "aws_rds_cluster" "aurora" {
  cluster_identifier     = "${local.name_prefix}-aurora"
  engine                 = "aurora-postgresql"
  engine_mode            = "provisioned"
  engine_version         = "16.4"
  database_name          = "velib"
  master_username        = "velib_app"
  master_password        = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.aurora.name
  vpc_security_group_ids = [aws_security_group.aurora.id]
  skip_final_snapshot    = true

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 4.0
  }

  tags = local.common_tags
}

resource "aws_rds_cluster_instance" "aurora" {
  cluster_identifier = aws_rds_cluster.aurora.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.aurora.engine
  engine_version     = aws_rds_cluster.aurora.engine_version
  publicly_accessible = true
  tags               = local.common_tags
}
# Outputs
output "api_endpoint" {
  value = aws_apigatewayv2_api.main.api_endpoint
}

output "s3_bucket" {
  value = aws_s3_bucket.velib_data.bucket
}

output "pipeline_lambda" {
  value = aws_lambda_function.pipeline.function_name
}
output "aurora_endpoint" {
  value     = aws_rds_cluster_instance.aurora.endpoint
  sensitive = true
}