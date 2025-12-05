# 音声対応AWS管理エージェント - 出力値

output "api_gateway_url" {
  description = "API GatewayのエンドポイントURL"
  value       = "${aws_api_gateway_rest_api.voice_api.execution_arn}/${var.environment}/voice-command"
}

output "api_gateway_invoke_url" {
  description = "API Gateway呼び出しURL"
  value       = "https://${aws_api_gateway_rest_api.voice_api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}/voice-command"
}

output "api_key_id" {
  description = "ElevenLabs用APIキーID"
  value       = aws_api_gateway_api_key.elevenlabs_key.id
}

output "api_key_value" {
  description = "ElevenLabs用APIキー値"
  value       = aws_api_gateway_api_key.elevenlabs_key.value
  sensitive   = true
}

output "lambda_function_name" {
  description = "Lambda関数名"
  value       = aws_lambda_function.voice_handler.function_name
}

output "lambda_function_arn" {
  description = "Lambda関数ARN"
  value       = aws_lambda_function.voice_handler.arn
}

output "cloudwatch_log_group" {
  description = "CloudWatchロググループ名"
  value       = aws_cloudwatch_log_group.voice_lambda_logs.name
}

output "iam_role_arn" {
  description = "Lambda実行ロールARN"
  value       = aws_iam_role.voice_lambda_role.arn
}

# ElevenLabs設定用の情報
output "elevenlabs_webhook_config" {
  description = "ElevenLabs Webhook設定情報"
  value = {
    webhook_url = "https://${aws_api_gateway_rest_api.voice_api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}/voice-command"
    api_key     = aws_api_gateway_api_key.elevenlabs_key.value
    headers = {
      "X-API-Key"    = aws_api_gateway_api_key.elevenlabs_key.value
      "Content-Type" = "application/json"
    }
  }
  sensitive = true
}

# Bedrock Agent情報
output "bedrock_agent_id" {
  description = "Bedrock AgentのID"
  value       = aws_bedrockagent_agent.voice_aws_agent.id
}

output "bedrock_agent_alias_id" {
  description = "Bedrock Agent AliasのID"
  value       = aws_bedrockagent_agent_alias.voice_aws_agent_alias.agent_alias_id
}

output "bedrock_agent_arn" {
  description = "Bedrock AgentのARN"
  value       = aws_bedrockagent_agent.voice_aws_agent.agent_arn
}
