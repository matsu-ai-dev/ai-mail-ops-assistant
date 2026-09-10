from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from fastapi.testclient import TestClient
from openai import OpenAIError

import api_app
import mail_classifier


SAMPLE_MAIL = {
    "subject": "【サンプル】旅行の予約確認",
    "sender": "sample@example.invalid",
    "body": "これはテスト用の架空の予約確認メールです。",
}


@pytest.fixture(autouse=True)
def isolate_external_services(monkeypatch):
    monkeypatch.setattr(api_app, "load_dotenv", Mock(return_value=False))
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-test-key")
    blocked_calls = []
    for target, name in [
        (mail_classifier.imaplib, "IMAP4_SSL"),
        (mail_classifier.imaplib, "IMAP4"),
        (mail_classifier, "main"),
        (mail_classifier, "process_one_mail"),
        (mail_classifier, "find_yahoo_folder"),
        (mail_classifier, "move_mail"),
        (mail_classifier, "write_log"),
    ]:
        blocked = Mock(side_effect=AssertionError(f"Unexpected call: {name}"))
        monkeypatch.setattr(target, name, blocked)
        blocked_calls.append(blocked)
    yield
    for blocked in blocked_calls:
        blocked.assert_not_called()


@pytest.fixture(autouse=True)
def ai_client(monkeypatch):
    client = MagicMock()
    client.__enter__.return_value = client
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="フォルダ候補：旅行"))]
    )
    monkeypatch.setattr(api_app, "OpenAI", Mock(return_value=client))
    return client


@pytest.fixture
def http_client():
    with TestClient(api_app.app) as client:
        yield client


def test_health_needs_no_credentials_or_ai(http_client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = http_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    api_app.OpenAI.assert_not_called()
    api_app.load_dotenv.assert_not_called()


@pytest.mark.parametrize(
    ("ai_response", "folder"),
    [
        ("要約：架空の予約確認です。\nフォルダ候補：旅行", "旅行"),
        ("フォルダ候補：\n旅行", "旅行"),
        ("分類：旅行", None),
        ("フォルダ候補：", None),
        ("フォルダ候補：\n　", None),
        ("フォルダ候補：通知不要なメール", "通知不要なメール"),
    ],
)
def test_classify_returns_folder_and_unmodified_ai_response(
    http_client, ai_client, ai_response, folder
):
    ai_client.chat.completions.create.return_value.choices[0].message.content = ai_response

    response = http_client.post("/classify", json=SAMPLE_MAIL)

    assert response.status_code == 200
    assert response.json() == {"folder": folder, "ai_response": ai_response}
    ai_client.chat.completions.create.assert_called_once()
    prompt = ai_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    for value in SAMPLE_MAIL.values():
        assert value in prompt
    ai_client.__exit__.assert_called_once()


def test_classify_reuses_existing_prompt_and_body_limit(http_client, ai_client):
    body = "あ" * 1000 + "この部分はAIに送られません"

    response = http_client.post("/classify", json={**SAMPLE_MAIL, "body": body})

    assert response.status_code == 200
    call = ai_client.chat.completions.create.call_args.kwargs
    assert call["model"] == "gpt-4o-mini"
    assert "あ" * 1000 in call["messages"][0]["content"]
    assert "この部分はAIに送られません" not in call["messages"][0]["content"]


@pytest.mark.parametrize("field", ["subject", "sender", "body"])
def test_classify_requires_each_field(http_client, field):
    payload = SAMPLE_MAIL.copy()
    del payload[field]

    response = http_client.post("/classify", json=payload)

    assert response.status_code == 422
    api_app.OpenAI.assert_not_called()


@pytest.mark.parametrize("field", ["subject", "sender", "body"])
@pytest.mark.parametrize("value", [None, 123, ["text"], {"text": "value"}])
def test_classify_requires_strings(http_client, field, value):
    response = http_client.post("/classify", json={**SAMPLE_MAIL, field: value})

    assert response.status_code == 422
    api_app.OpenAI.assert_not_called()


def test_classify_without_api_key_returns_503(http_client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = http_client.post("/classify", json=SAMPLE_MAIL)

    assert response.status_code == 503
    assert response.json() == {"detail": "OPENAI_API_KEY is not configured"}
    api_app.OpenAI.assert_not_called()


def test_classify_ai_failure_returns_generic_error(http_client, ai_client):
    ai_client.chat.completions.create.side_effect = OpenAIError(
        "dummy upstream error with details that must not be returned"
    )

    response = http_client.post("/classify", json=SAMPLE_MAIL)

    assert response.status_code == 502
    assert response.json() == {"detail": "AI classification failed"}
    ai_client.__exit__.assert_called_once()


@pytest.mark.parametrize("content", [None, "", " \n "])
def test_classify_without_ai_text_returns_502(http_client, ai_client, content):
    ai_client.chat.completions.create.return_value.choices[0].message.content = content

    response = http_client.post("/classify", json=SAMPLE_MAIL)

    assert response.status_code == 502
    assert response.json() == {"detail": "AI returned no text"}
