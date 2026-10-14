
import json
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv


class SecretLoadError(RuntimeError):
    """APIキーの取得に失敗したことを表す例外。"""
    pass


def get_openai_api_key():
    # AWS Lambda上ではSecrets Managerから取得
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        try:
            client = boto3.client(
                "secretsmanager",
                region_name="ap-northeast-1"
            )

            response = client.get_secret_value(
                SecretId="vision-desc-openai"
            )

            secret = json.loads(response["SecretString"])
            api_key = secret["OPENAI_API_KEY"]

            if not isinstance(api_key, str) or not api_key.strip():
                raise ValueError("Invalid API key")

            return api_key.strip()

        except (BotoCoreError, ClientError, KeyError,
                TypeError, ValueError):
            # AWSの内部エラーや秘密情報を呼び出し元に渡さない
            raise SecretLoadError(
                "OpenAI credentials unavailable"
            ) from None

    # ローカルPCでは従来の.envを使用
    load_dotenv()
    return os.getenv("OPENAI_API_KEY")
