# 音声対応AWS管理エージェント - 変数定義

variable "aws_region" {
  description = "AWSリージョン"
  type        = string
  default     = "ap-northeast-1"
}

variable "environment" {
  description = "環境名（dev, staging, prod）"
  type        = string
  default     = "dev"
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "環境は dev, staging, prod のいずれかである必要があります。"
  }
}

variable "log_level" {
  description = "ログレベル"
  type        = string
  default     = "INFO"
  
  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR"], var.log_level)
    error_message = "ログレベルは DEBUG, INFO, WARNING, ERROR のいずれかである必要があります。"
  }
}

variable "project_name" {
  description = "プロジェクト名"
  type        = string
  default     = "voice-aws-agent"
}

variable "allowed_origins" {
  description = "CORS許可オリジン"
  type        = list(string)
  default     = ["*"]
}

variable "api_throttle_rate" {
  description = "API スロットリング レート（リクエスト/秒）"
  type        = number
  default     = 10
}

variable "api_throttle_burst" {
  description = "API スロットリング バースト制限"
  type        = number
  default     = 20
}

variable "lambda_timeout" {
  description = "Lambda関数のタイムアウト（秒）"
  type        = number
  default     = 30
}

variable "lambda_memory_size" {
  description = "Lambda関数のメモリサイズ（MB）"
  type        = number
  default     = 256
}

variable "log_retention_days" {
  description = "CloudWatchログの保持期間（日）"
  type        = number
  default     = 14
}