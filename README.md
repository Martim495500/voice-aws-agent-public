# Voice AWS Agent

ElevenLabsの音声エージェントとAWS Bedrockを統合し、音声指示でAWSリソースを管理・監視できるシステムです。

## 🎯 主な機能

### 1. 全AWSサービスの読み取り専用アクセス
- **200+ AWSサービス対応**: EC2, S3, Lambda, RDS, DynamoDB, ECS, ELB, CloudWatch, など
- **動的コード生成**: Bedrockが音声指示から直接boto3コードを生成
- **柔軟な対応**: 新しいAWSサービスに自動対応

### 2. 詳細なコスト分析機能
- **今月のコスト**: 月初から現在までの総コスト
- **サービス別内訳**: 使用料の高いサービスTOP10
- **不要リソース検出**: 低使用サービスの自動検出
- **期間指定**: 今月、先月、今週、先週、過去7日/30日

### 3. セキュリティ重視設計
- **厳密な読み取り専用**: リソースの削除・変更は完全ブロック
- **多層検証**: AI層とコード層の2段階検証
- **ホワイトリスト方式**: describe*, list*, get* のみ許可

## 🚀 クイックスタート

### 前提条件
- AWSアカウント（Cost Explorer有効化済み）
- Terraform >= 1.0
- AWS CLI設定済み
- ElevenLabsアカウント

### 1. リポジトリのクローン

```bash
git clone <your-repo-url>
cd voice-aws-agent
```

### 2. AWS認証情報の設定

```bash
aws configure
```

### 3. Terraformでデプロイ

```bash
cd terraform
terraform init
terraform apply
```

デプロイ後、以下の情報が出力されます：
- API Gateway URL
- API Key
- Bedrock Agent ID

### 4. ElevenLabs設定

1. `elevenlabs-webhook-config.example.json`をコピーして`elevenlabs-webhook-config.json`を作成
2. 以下の値を実際の値に置き換え：
   - `YOUR_API_GATEWAY_URL`: Terraformの出力から取得
   - `YOUR_SECRET_ID`: ElevenLabsで作成したSecret ID

3. ElevenLabsのAgent設定画面でWebhookを設定

詳細は [elevenlabs-agent-prompt.md](./elevenlabs-agent-prompt.md) を参照してください。

## 📊 使用例

### リソース確認
```
「EC2インスタンスの状態を確認して」
「S3バケットの一覧を見せて」
「Lambda関数を教えて」
「RDSデータベースの状態は？」
```

### コスト分析
```
「今月のAWSコストを教えて」
「使用料の高いサービスは？」
「不要なリソースを教えて」
「先月のコストを確認して」
```

## 🏗️ アーキテクチャ

```
ElevenLabs音声エージェント
    ↓ (Webhook)
API Gateway (認証)
    ↓
Lambda関数
    ├→ Bedrock (boto3コード生成)
    ├→ SafeExecutor (セキュリティ検証)
    ├→ Cost Explorer (コスト取得)
    └→ AWS各種サービス (読み取り)
```

## 📁 プロジェクト構造

```
voice-aws-agent/
├── src/
│   └── lambda/
│       └── voice_handler.py          # Lambda関数メインコード
├── terraform/
│   ├── main.tf                       # メインTerraform設定
│   ├── bedrock.tf                    # Bedrock Agent設定
│   ├── outputs.tf                    # 出力値定義
│   └── variables.tf                  # 変数定義
├── iam/
│   ├── runtime-policy.json           # Lambda実行時権限
│   └── deployment-policy.json        # デプロイ用権限
├── elevenlabs-agent-prompt.md        # ElevenLabsプロンプト
├── elevenlabs-webhook-config.example.json  # Webhook設定例
└── README.md                         # このファイル
```

## 🔒 セキュリティ

### 実装済みのセキュリティ対策

1. **読み取り専用ポリシー**
   - `Describe*`, `List*`, `Get*` のみ許可
   - 書き込み操作は全て禁止

2. **コード検証**
   - 禁止パターンの自動検出
   - boto3呼び出しのみを厳密にチェック

3. **API認証**
   - API Keyによる認証
   - 使用量制限（1000req/日）

4. **監査ログ**
   - 全操作をCloudWatch Logsに記録
   - 14日間保持

## 📊 コスト

### 月額推定コスト（東京リージョン）

- **Lambda**: $0.20 (1000リクエスト/月)
- **API Gateway**: $3.50 (1000リクエスト/月)
- **Bedrock**: $3.00 (Claude 3.5 Sonnet使用)
- **CloudWatch Logs**: $0.50 (1GB/月)
- **Cost Explorer API**: $0.01 (100リクエスト/月)

**合計**: 約 $7.21/月

## 🛠️ トラブルシューティング

### Cost Explorerのデータが空

**原因**: データは最大24時間遅延します

**対処法**: 「過去30日のコストを教えて」と聞く

### タイムアウトエラー

**原因**: 複数のAPI呼び出しで時間がかかる

**対処法**: 不要リソース検出はCost Explorerのみを使用（自動最適化済み）

## 📄 ライセンス

MIT License

## 🤝 コントリビューション

プルリクエストを歓迎します！

1. このリポジトリをフォーク
2. フィーチャーブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing-feature`)
5. プルリクエストを作成

## ⚠️ 注意事項

- **本番環境での使用**: 読み取り専用ですが、機密情報へのアクセスが可能です
- **コスト管理**: Cost Explorer APIは有料です（$0.01/リクエスト）
- **データの遅延**: Cost Explorerのデータは最大24時間遅延します
- **リージョン**: EC2等のリソースはap-northeast-1（東京）のみ確認
