"""
音声指示を受信してAWS操作を実行するLambda関数
ElevenLabsからの音声指示をBedrockで解析し、適切なAWS APIを呼び出す
Bedrockが生成したboto3コードを安全に実行する方式
"""

import json
import boto3
import logging
import os
import re
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from io import StringIO
import sys

# ログ設定
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class SafeExecutor:
    """Bedrockが生成したコードを安全に実行するクラス"""
    
    def __init__(self):
        # 許可されたモジュールとクライアント
        self.allowed_modules = {
            'boto3': boto3,
            'datetime': datetime,
            'timedelta': timedelta,
            'json': json,
        }
        
        # 禁止されたキーワード（セキュリティ）
        self.forbidden_keywords = [
            'exec', 'eval', 'compile', '__import__',
            'open', 'file', 'input', 'raw_input',
            'delete', 'terminate', 'destroy', 'remove',
            'stop_instances', 'delete_', 'terminate_',
        ]
    
    def validate_code(self, code: str) -> bool:
        """生成されたコードの安全性を検証（厳密版）"""
        code_lower = code.lower()
        
        # 禁止キーワードのチェック
        for keyword in self.forbidden_keywords:
            if keyword in code_lower:
                logger.warning(f"禁止されたキーワードを検出: {keyword}")
                return False
        
        # 書き込み操作の完全なリスト（AWS APIの命名規則に基づく）
        write_operations = [
            # 作成系
            'create', 'run_instances', 'launch', 'start', 'allocate', 'associate',
            'attach', 'register', 'add', 'enable', 'activate', 'provision',
            
            # 更新系
            'update', 'modify', 'change', 'set', 'put', 'patch', 'edit',
            'replace', 'reboot', 'reset', 'restore', 'revoke',
            
            # 削除系
            'delete', 'remove', 'terminate', 'stop', 'destroy', 'deregister',
            'detach', 'disassociate', 'disable', 'deactivate', 'cancel',
            'release', 'revoke',
            
            # その他の危険な操作
            'import', 'export', 'copy', 'snapshot', 'backup', 'restore',
            'authorize', 'purchase', 'accept', 'reject', 'apply'
        ]
        
        # コード内の全てのメソッド呼び出しを抽出（オブジェクト名も含む）
        method_calls = re.findall(r'(\w+)\.(\w+)\s*\(', code)
        
        for obj, method in method_calls:
            method_lower = method.lower()
            obj_lower = obj.lower()
            
            # boto3クライアントのメソッドのみチェック（日付操作などは除外）
            is_boto3_call = obj_lower in ['ec2', 's3', 'rds', 'lambda_client', 'ce', 'dynamodb', 
                                          'ecs', 'elb', 'iam', 'kms', 'sns', 'sqs', 'cloudwatch',
                                          'cloudfront', 'route53', 'apigateway', 'client']
            
            # boto3呼び出しの場合のみ書き込み操作をチェック
            if is_boto3_call:
                for operation in write_operations:
                    if operation in method_lower:
                        logger.warning(f"書き込み操作を検出: {obj}.{method}")
                        return False
            
            # boto3呼び出しの場合のみホワイトリストチェック
            if is_boto3_call:
                # 読み取り専用操作のホワイトリスト
                allowed_prefixes = ['describe', 'list', 'get', 'query', 'search', 'lookup']
                is_allowed = any(method_lower.startswith(prefix) for prefix in allowed_prefixes)
                
                # boto3クライアント作成は許可
                if method_lower in ['client', 'resource', 'session']:
                    is_allowed = True
                
                if not is_allowed:
                    logger.warning(f"許可されていないAWS API: {obj}.{method}")
                    return False
        
        return True
    
    def execute(self, code: str) -> Dict[str, Any]:
        """生成されたコードを安全に実行"""
        try:
            # コードの検証
            if not self.validate_code(code):
                return {
                    'success': False,
                    'error': 'Security validation failed: Code contains forbidden operations'
                }
            
            # 実行環境の準備
            local_vars = {}
            global_vars = {
                'boto3': boto3,
                'datetime': datetime,
                'timedelta': timedelta,
                'json': json,
            }
            
            # 標準出力をキャプチャ
            old_stdout = sys.stdout
            sys.stdout = captured_output = StringIO()
            
            try:
                # コードを実行
                exec(code, global_vars, local_vars)
                
                # 結果を取得
                result = local_vars.get('result', {})
                
                # 標準出力も取得
                output = captured_output.getvalue()
                if output:
                    result['output'] = output
                
                return {
                    'success': True,
                    'result': result
                }
                
            finally:
                sys.stdout = old_stdout
                
        except Exception as e:
            logger.error(f"コード実行エラー: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }

class AWSVoiceAgent:
    """音声指示でAWS操作を行うエージェント（Bedrock駆動型）"""
    
    def __init__(self):
        self.bedrock_runtime = boto3.client('bedrock-runtime', region_name='ap-northeast-1')
        self.executor = SafeExecutor()
    
    def generate_aws_code(self, instruction: str) -> str:
        """
        Bedrockを使用して音声指示からboto3コードを生成
        """
        try:
            prompt = f"""
あなたはAWS操作のエキスパートです。ユーザーの音声指示を理解し、適切なboto3コードを生成してください。

## ユーザーの指示
{instruction}

## 生成ルール
1. **読み取り専用操作のみ**: describe_*, list_*, get_*, query_*, search_* メソッドのみ使用
2. **厳密に禁止される操作**:
   - 作成系: create*, run_instances, launch*, start*, allocate*, associate*, attach*, register*, add*, enable*, activate*
   - 更新系: update*, modify*, change*, set*, put*, patch*, edit*, replace*, reboot*, reset*, restore*, revoke*
   - 削除系: delete*, remove*, terminate*, stop*, destroy*, deregister*, detach*, disassociate*, disable*, deactivate*, cancel*, release*
   - その他: import*, export*, copy*, snapshot*, backup*, authorize*, purchase*, accept*, reject*, apply*
3. **結果の格納**: 必ず `result` 変数に結果を辞書形式で格納
4. **エラーハンドリング**: try-except で適切にエラー処理
5. **簡潔な実装**: 必要最小限のコードのみ
6. **コメント**: 日本語でコメントを追加
7. **重要**: 上記の禁止操作を含むコードは絶対に生成しないでください
8. **パフォーマンス**: 
   - 不要リソース検出は**Cost Explorerのみ**を使用（低コストサービスを検出）
   - 複数サービスのAPI呼び出しは避ける（タイムアウトの原因）
   - 必要最小限のデータのみ取得

## コスト分析の場合
- Cost Explorer APIを使用（us-east-1リージョン）
- 期間指定に対応:
  - 「今月」→ 月初から今日まで（データがない場合は過去30日）
  - 「先月」→ 先月の1日から末日まで
  - 「今週」→ 今週の月曜から今日まで
  - 「先週」→ 先週の月曜から日曜まで
  - 「過去7日」「過去30日」→ 指定日数前から今日まで
- サービス別コスト、TOP10を含める
- **重要**: get_cost_forecastは複雑でエラーが出やすいため、基本的には使用しないでください
- **重要**: 必ず堅牢なエラーハンドリングを実装してください
- **重要**: データが空の場合も適切に処理してください

## 出力形式
Pythonコードのみを出力してください。説明文やマークダウンは不要です。

## コード例

### EC2インスタンス確認の例
```python
import boto3

# EC2クライアント作成
ec2 = boto3.client('ec2')

try:
    # インスタンス情報を取得
    response = ec2.describe_instances()
    
    instances = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instances.append({{
                'InstanceId': instance['InstanceId'],
                'State': instance['State']['Name'],
                'InstanceType': instance['InstanceType']
            }})
    
    result = {{
        'success': True,
        'count': len(instances),
        'instances': instances
    }}
except Exception as e:
    result = {{
        'success': False,
        'error': str(e)
    }}
```

### コスト分析の例（最も堅牢な実装）
```python
import boto3
from datetime import datetime, timedelta

# Cost Explorer クライアント（us-east-1のみ）
ce = boto3.client('ce', region_name='us-east-1')

try:
    # 期間設定（過去30日が最も確実）
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    
    # Cost Explorer APIを呼び出し
    response = ce.get_cost_and_usage(
        TimePeriod={{
            'Start': start_date.strftime('%Y-%m-%d'),
            'End': end_date.strftime('%Y-%m-%d')
        }},
        Granularity='MONTHLY',
        Metrics=['UnblendedCost'],
        GroupBy=[{{'Type': 'DIMENSION', 'Key': 'SERVICE'}}]
    )
    
    # サービス別コストを集計
    service_costs = []
    total_cost = 0
    
    # 安全にデータを取得
    if 'ResultsByTime' in response and response['ResultsByTime']:
        for time_result in response['ResultsByTime']:
            if 'Groups' in time_result and time_result['Groups']:
                for group in time_result['Groups']:
                    try:
                        service_name = group['Keys'][0] if 'Keys' in group and group['Keys'] else 'Unknown'
                        cost_data = group.get('Metrics', {{}}).get('UnblendedCost', {{}})
                        cost = float(cost_data.get('Amount', 0))
                        
                        if cost > 0.01:
                            service_costs.append({{
                                'service': service_name,
                                'cost': round(cost, 2)
                            }})
                            total_cost += cost
                    except (KeyError, ValueError, TypeError) as e:
                        continue  # スキップして次へ
    
    # コストの高い順にソート
    service_costs.sort(key=lambda x: x['cost'], reverse=True)
    
    result = {{
        'success': True,
        'total_cost': round(total_cost, 2),
        'currency': 'USD',
        'period': {{
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        }},
        'top_services': service_costs[:10],
        'all_services_count': len(service_costs),
        'data_note': 'Showing last 30 days. Cost Explorer data may be delayed up to 24 hours.'
    }}
    
except Exception as e:
    result = {{
        'success': False,
        'error': str(e),
        'error_type': type(e).__name__
    }}
```

**必ず守るべきルール**:
1. get_cost_forecastは使用しない（エラーが多い）
2. 期間は過去30日が最も確実
3. 全てのデータアクセスでKeyError対策
4. try-exceptで個別のグループ処理を保護
5. データが空でもエラーにしない

重要な注意点:
- Cost Explorerのデータは最大24時間遅延します
- GroupByを使用する場合、response['ResultsByTime'][0]['Total']は存在しません
- 必ず'ResultsByTime'と'Groups'の存在チェックを行ってください
- エラーハンドリングは必須です
- get_cost_forecastは省略可能です（エラーが出やすいため）
- 月末日の計算は複雑なので、単純に+30日で十分です

月末予測が必要な場合の正しい実装:
```python
# 月末予測（オプション - エラーが出る場合はスキップ）
try:
    next_month_start = (end_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    forecast_response = ce.get_cost_forecast(
        TimePeriod={{
            'Start': (end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
            'End': next_month_start.strftime('%Y-%m-%d')
        }},
        Metric='UNBLENDED_COST',
        Granularity='MONTHLY'
    )
    forecast_cost = round(float(forecast_response['Total']['Amount']), 2)
except:
    forecast_cost = None  # 予測が取得できない場合はNone
```

### 不要リソース検出の例（効率的な実装）
```python
import boto3
from datetime import datetime, timedelta

# Cost Explorer のみ使用（高速）
ce = boto3.client('ce', region_name='us-east-1')

try:
    # 過去30日のコストを取得
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    
    response = ce.get_cost_and_usage(
        TimePeriod={{
            'Start': start_date.strftime('%Y-%m-%d'),
            'End': end_date.strftime('%Y-%m-%d')
        }},
        Granularity='MONTHLY',
        Metrics=['UnblendedCost'],
        GroupBy=[{{'Type': 'DIMENSION', 'Key': 'SERVICE'}}]
    )
    
    # 低コストサービスを検出（$1未満）
    low_cost_services = []
    total_cost = 0
    
    if 'ResultsByTime' in response and response['ResultsByTime']:
        for group in response['ResultsByTime'][0]['Groups']:
            service_name = group['Keys'][0]
            cost = float(group['Metrics']['UnblendedCost']['Amount'])
            total_cost += cost
            
            # $1未満のサービスを不要候補として検出
            if 0.01 < cost < 1.0:
                low_cost_services.append({{
                    'service': service_name,
                    'cost': round(cost, 2),
                    'recommendation': 'Consider if this service is still needed'
                }})
    
    result = {{
        'success': True,
        'total_cost': round(total_cost, 2),
        'currency': 'USD',
        'unused_candidates': low_cost_services,
        'unused_count': len(low_cost_services),
        'note': 'Services with very low usage (under $1/month)'
    }}
except Exception as e:
    result = {{
        'success': False,
        'error': str(e)
    }}
```

重要: 不要リソース検出は**Cost Explorerのみ**を使用してください。
EC2やS3などの個別API呼び出しは時間がかかりタイムアウトの原因になります。

それでは、ユーザーの指示に基づいてコードを生成してください。
"""
            
            response = self.bedrock_runtime.invoke_model(
                modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
                body=json.dumps({
                    'anthropic_version': 'bedrock-2023-05-31',
                    'max_tokens': 2000,
                    'messages': [{'role': 'user', 'content': prompt}]
                })
            )
            
            result = json.loads(response['body'].read())
            content = result['content'][0]['text']
            
            # コードブロックから抽出
            if '```python' in content:
                code = content.split('```python')[1].split('```')[0].strip()
            elif '```' in content:
                code = content.split('```')[1].split('```')[0].strip()
            else:
                code = content.strip()
            
            logger.info(f"生成されたコード:\n{code}")
            return code
            
        except Exception as e:
            logger.error(f"コード生成エラー: {e}")
            raise
    
    def execute_instruction(self, instruction: str) -> Dict[str, Any]:
        """
        音声指示を実行
        """
        try:
            # Bedrockでコード生成
            code = self.generate_aws_code(instruction)
            
            # コードを安全に実行
            execution_result = self.executor.execute(code)
            
            if execution_result['success']:
                return {
                    'success': True,
                    'instruction': instruction,
                    'result': execution_result['result'],
                    'generated_code': code
                }
            else:
                return {
                    'success': False,
                    'instruction': instruction,
                    'error': execution_result.get('error'),
                    'error_type': execution_result.get('error_type'),
                    'generated_code': code
                }
                
        except Exception as e:
            logger.error(f"指示実行エラー: {e}")
            return {
                'success': False,
                'instruction': instruction,
                'error': str(e),
                'error_type': type(e).__name__
            }

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda関数のメインハンドラー
    ElevenLabsからの音声指示を処理
    """
    try:
        # ElevenLabsからのペイロード解析
        body = json.loads(event.get('body', '{}'))
        
        # 音声指示を取得（複数のフィールド名に対応）
        voice_instruction = (
            body.get('command') or
            body.get('instruction') or
            body.get('text') or
            body.get('message') or
            body.get('input') or
            body.get('query') or
            ''
        )
        
        logger.info(f"受信ペイロード: {json.dumps(body, ensure_ascii=False)}")
        
        if not voice_instruction:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': '音声指示が見つかりません',
                    'message': 'command, instruction, text, message, input, queryのいずれかのフィールドが必要です',
                    'received_body': body
                }, ensure_ascii=False)
            }
        
        # 音声エージェント初期化
        agent = AWSVoiceAgent()
        
        # 指示を実行
        result = agent.execute_instruction(voice_instruction)
        
        logger.info(f"実行結果: {json.dumps(result, ensure_ascii=False, default=str)}")
        
        if result['success']:
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': True,
                    'instruction': voice_instruction,
                    'result': result['result']
                }, ensure_ascii=False, default=str)
            }
        else:
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'instruction': voice_instruction,
                    'error': result.get('error'),
                    'error_type': result.get('error_type')
                }, ensure_ascii=False)
            }
        
    except Exception as e:
        logger.error(f"処理エラー: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': '内部サーバーエラー',
                'message': str(e)
            })
        }
