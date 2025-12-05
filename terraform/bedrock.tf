# Bedrock設定

# Note: Bedrockモデルアクセスは手動で有効化が必要
# AWS Console → Bedrock → Model access → Request model access
# 必要なモデル: Claude 3 Sonnet (anthropic.claude-3-sonnet-20240229-v1:0)

# Bedrock Agent用のIAMロール
resource "aws_iam_role" "bedrock_agent_role" {
  name = "voice-aws-agent-bedrock-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "voice-aws-agent-bedrock-role"
    Component   = "IAM"
    Description = "Bedrock Agent Execution Role"
  }
}

# Bedrockがモデルを呼び出す権限
resource "aws_iam_role_policy" "bedrock_model_invocation" {
  name = "bedrock-model-invocation-policy"
  role = aws_iam_role.bedrock_agent_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/*"
        ]
      }
    ]
  })
}

# Bedrock Agent
resource "aws_bedrockagent_agent" "voice_aws_agent" {
  agent_name              = "voice-aws-agent"
  agent_resource_role_arn = aws_iam_role.bedrock_agent_role.arn
  foundation_model        = "anthropic.claude-3-haiku-20240307-v1:0"
  
  instruction = <<-EOT
    あなたは日本語で音声指示を理解し、AWS操作コマンドに変換するエージェントです。
    
    ユーザーからの音声指示を受け取り、以下のJSON形式で応答してください：
    {
      "service": "ec2|s3|lambda|cloudwatch",
      "action": "具体的なAWSアクション名",
      "resource": "対象リソース（あれば）",
      "parameters": {"key": "value"}
    }
    
    例：
    - 「EC2インスタンスの状態を確認して」→ {"service": "ec2", "action": "describe-instances"}
    - 「新しいS3バケットを作成して」→ {"service": "s3", "action": "create-bucket"}
    
    セキュリティ上、以下の操作は絶対に提案しないでください：
    - delete, terminate, destroy, remove を含む操作
    - 本番環境への変更
    - 認証情報の変更
  EOT
  
  idle_session_ttl_in_seconds = 600

  tags = {
    Name        = "voice-aws-agent"
    Component   = "Bedrock"
    Description = "Voice Command Processing AI Agent"
  }
}

# Bedrock Agent Alias (デプロイ用)
resource "aws_bedrockagent_agent_alias" "voice_aws_agent_alias" {
  agent_id         = aws_bedrockagent_agent.voice_aws_agent.id
  agent_alias_name = "production"
  description      = "Production alias for voice AWS agent"
}
