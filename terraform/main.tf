# 音声対応AWS管理エージェントのTerraform設定

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "voice-aws-agent"
      Environment = var.environment
      ManagedBy   = "terraform"
      CreatedBy   = "terraform"
    }
  }
}

# 現在のAWSアカウント情報
data "aws_caller_identity" "current" {}

# Lambda関数用のZIPファイル作成
data "archive_file" "voice_handler_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/lambda"
  output_path = "${path.module}/voice_handler.zip"
}

# Lambda実行ロール
resource "aws_iam_role" "voice_lambda_role" {
  name = "voice-aws-agent-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "voice-aws-agent-lambda-role"
    Component   = "IAM"
    Description = "Lambda実行ロール"
  }
}

# Lambda基本実行ポリシー
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.voice_lambda_role.name
}

# AWS操作用のカスタムポリシー（読み取り専用 + Cost Explorer）
resource "aws_iam_role_policy" "voice_aws_operations" {
  name = "voice-aws-operations-policy"
  role = aws_iam_role.voice_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          # 全サービスの読み取り専用アクセス
          "ec2:Describe*",
          "s3:List*",
          "s3:Get*",
          "lambda:List*",
          "lambda:Get*",
          "cloudwatch:Describe*",
          "cloudwatch:Get*",
          "cloudwatch:List*",
          "rds:Describe*",
          "dynamodb:Describe*",
          "dynamodb:List*",
          "ecs:Describe*",
          "ecs:List*",
          "eks:Describe*",
          "eks:List*",
          "elasticache:Describe*",
          "elasticache:List*",
          "elasticloadbalancing:Describe*",
          "autoscaling:Describe*",
          "cloudformation:Describe*",
          "cloudformation:List*",
          "cloudfront:List*",
          "cloudfront:Get*",
          "route53:List*",
          "route53:Get*",
          "sns:List*",
          "sns:Get*",
          "sqs:List*",
          "sqs:Get*",
          "apigateway:GET",
          "iam:List*",
          "iam:Get*",
          "kms:List*",
          "kms:Describe*",
          "secretsmanager:List*",
          "secretsmanager:Describe*",
          "ssm:Describe*",
          "ssm:List*",
          "ssm:Get*",
          "backup:List*",
          "backup:Describe*",
          "organizations:Describe*",
          "organizations:List*",
          "tag:Get*"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          # Cost Explorer API
          "ce:GetCostAndUsage",
          "ce:GetCostForecast",
          "ce:GetDimensionValues",
          "ce:GetTags",
          "ce:GetReservationUtilization",
          "ce:GetSavingsPlansUtilization",
          "ce:GetRightsizingRecommendation",
          "ce:GetCostCategories"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:*"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "aws-marketplace:ViewSubscriptions",
          "aws-marketplace:Subscribe"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda関数
resource "aws_lambda_function" "voice_handler" {
  filename         = data.archive_file.voice_handler_zip.output_path
  function_name    = "voice-aws-agent-handler"
  role            = aws_iam_role.voice_lambda_role.arn
  handler         = "voice_handler.lambda_handler"
  runtime         = "python3.11"
  timeout         = 60
  memory_size     = 512

  source_code_hash = data.archive_file.voice_handler_zip.output_base64sha256

  environment {
    variables = {
      LOG_LEVEL              = var.log_level
      ENVIRONMENT            = var.environment
      BEDROCK_AGENT_ID       = aws_bedrockagent_agent.voice_aws_agent.id
      BEDROCK_AGENT_ALIAS_ID = aws_bedrockagent_agent_alias.voice_aws_agent_alias.agent_alias_id
    }
  }

  tags = {
    Name        = "voice-aws-agent-handler"
    Component   = "Lambda"
    Description = "音声指示処理Lambda関数"
  }
}

# API Gateway REST API
resource "aws_api_gateway_rest_api" "voice_api" {
  name        = "voice-aws-agent-api"
  description = "ElevenLabs音声エージェント用API"
  
  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Name        = "voice-aws-agent-api"
    Component   = "APIGateway"
    Description = "音声エージェント用REST API"
  }
}

# API Gateway リソース
resource "aws_api_gateway_resource" "voice_command" {
  rest_api_id = aws_api_gateway_rest_api.voice_api.id
  parent_id   = aws_api_gateway_rest_api.voice_api.root_resource_id
  path_part   = "voice-command"
}

# API Gateway メソッド
resource "aws_api_gateway_method" "post_voice_command" {
  rest_api_id   = aws_api_gateway_rest_api.voice_api.id
  resource_id   = aws_api_gateway_resource.voice_command.id
  http_method   = "POST"
  authorization = "NONE"
  
  request_parameters = {
    "method.request.header.X-API-Key" = true
  }
}

# API Gateway統合
resource "aws_api_gateway_integration" "lambda_integration" {
  rest_api_id = aws_api_gateway_rest_api.voice_api.id
  resource_id = aws_api_gateway_resource.voice_command.id
  http_method = aws_api_gateway_method.post_voice_command.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.voice_handler.invoke_arn
}

# Lambda実行権限
resource "aws_lambda_permission" "api_gateway_invoke" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.voice_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.voice_api.execution_arn}/*/*"
}

# API Gatewayデプロイメント
resource "aws_api_gateway_deployment" "voice_api_deployment" {
  depends_on = [
    aws_api_gateway_method.post_voice_command,
    aws_api_gateway_integration.lambda_integration
  ]

  rest_api_id = aws_api_gateway_rest_api.voice_api.id
}

# API Gatewayステージ
resource "aws_api_gateway_stage" "voice_api_stage" {
  deployment_id = aws_api_gateway_deployment.voice_api_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.voice_api.id
  stage_name    = var.environment

  tags = {
    Name        = "voice-aws-agent-${var.environment}-stage"
    Component   = "APIGateway"
    Description = "APIステージ"
  }
}

# API Key
resource "aws_api_gateway_api_key" "elevenlabs_key" {
  name        = "elevenlabs-voice-agent-key"
  description = "ElevenLabs音声エージェント用APIキー"

  tags = {
    Name        = "elevenlabs-voice-agent-key"
    Component   = "APIGateway"
    Description = "ElevenLabs用APIキー"
  }
}

# Usage Plan
resource "aws_api_gateway_usage_plan" "voice_usage_plan" {
  name = "voice-agent-usage-plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.voice_api.id
    stage  = aws_api_gateway_stage.voice_api_stage.stage_name
  }

  quota_settings {
    limit  = 1000
    period = "DAY"
  }

  throttle_settings {
    rate_limit  = 10
    burst_limit = 20
  }

  tags = {
    Name        = "voice-agent-usage-plan"
    Component   = "APIGateway"
    Description = "使用量プラン"
  }
}

# Usage Plan Key
resource "aws_api_gateway_usage_plan_key" "voice_usage_plan_key" {
  key_id        = aws_api_gateway_api_key.elevenlabs_key.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.voice_usage_plan.id
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "voice_lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.voice_handler.function_name}"
  retention_in_days = 14

  tags = {
    Name        = "voice-aws-agent-lambda-logs"
    Component   = "CloudWatch"
    Description = "Lambda関数ログ"
  }
}