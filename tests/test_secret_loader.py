import pytest
from botocore.exceptions import ClientError

from unittest.mock import Mock

import secret_loader


def test_local_api_key(monkeypatch):
    # ローカルPCで動いている状態を再現
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-local-key")
    monkeypatch.setattr(secret_loader, "load_dotenv", Mock())

    # AWSへの接続は許可しない
    monkeypatch.setattr(
        secret_loader.boto3,
        "client",
        Mock(side_effect=AssertionError("Unexpected AWS access"))
    )

    result = secret_loader.get_openai_api_key()

    assert result == "dummy-local-key"


def test_lambda_api_key(monkeypatch):
    # Lambdaで動いている状態を再現
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "ai-mail-ops-api")

    # Secrets Managerの偽物の応答
    mock_client = Mock()
    mock_client.get_secret_value.return_value = {
        "SecretString": '{"OPENAI_API_KEY":"dummy-aws-key"}'
    }

    mock_factory = Mock(return_value=mock_client)
    monkeypatch.setattr(
        secret_loader.boto3,
        "client",
        mock_factory
    )

    result = secret_loader.get_openai_api_key()

    assert result == "dummy-aws-key"

    # 正しいリージョンとシークレット名か確認
    mock_factory.assert_called_once_with(
        "secretsmanager",
        region_name="ap-northeast-1"
    )

    mock_client.get_secret_value.assert_called_once_with(
        SecretId="vision-desc-openai"
    )


def test_lambda_access_denied(monkeypatch):
    # Lambda環境を再現
    monkeypatch.setenv(
        "AWS_LAMBDA_FUNCTION_NAME",
        "ai-mail-ops-api"
    )

    # IAM権限不足のエラーを再現
    mock_client = Mock()
    mock_client.get_secret_value.side_effect = ClientError(
        {
            "Error": {
                "Code": "AccessDeniedException",
                "Message": "Private AWS error details"
            }
        },
        "GetSecretValue"
    )

    monkeypatch.setattr(
        secret_loader.boto3,
        "client",
        Mock(return_value=mock_client)
    )

    # 詳細情報を含まない共通エラーに変換されるか
    with pytest.raises(secret_loader.SecretLoadError) as exc:
        secret_loader.get_openai_api_key()

    assert str(exc.value) == "OpenAI credentials unavailable"


@pytest.mark.parametrize("secret_text", [
    "{invalid-json",
    "{}"
])
def test_lambda_invalid_secret(monkeypatch, secret_text):
    # Lambda環境を再現
    monkeypatch.setenv(
        "AWS_LAMBDA_FUNCTION_NAME",
        "ai-mail-ops-api"
    )

    # 不正なシークレットを返す
    mock_client = Mock()
    mock_client.get_secret_value.return_value = {
        "SecretString": secret_text
    }

    monkeypatch.setattr(
        secret_loader.boto3,
        "client",
        Mock(return_value=mock_client)
    )

    with pytest.raises(
        secret_loader.SecretLoadError,
        match="OpenAI credentials unavailable"
    ):
        secret_loader.get_openai_api_key()