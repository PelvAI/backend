"""Timeout de upload RAG é independente do timeout do chat."""

import pytest

from app.core.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _FakeChatbotResponse:
    status_code = 200
    content = b'{"ok": true, "uploaded": []}'
    headers = {"content-type": "application/json"}


@pytest.mark.asyncio
async def test_rag_upload_uses_chatbot_upload_timeout(client, monkeypatch):
    monkeypatch.setenv("CHATBOT_SERVICE_TOKEN", "test-token-32chars-minimum-xxxxx")
    monkeypatch.setenv("CHATBOT_TIMEOUT_SECONDS", "120")
    monkeypatch.setenv("CHATBOT_UPLOAD_TIMEOUT_SECONDS", "600")
    monkeypatch.setenv("ENVIRONMENT", "development")
    get_settings.cache_clear()

    captured: dict = {}

    class FakeAsyncClient:
        def __init__(self, *args, timeout=None, **kwargs):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, files=None):
            captured["url"] = url
            return _FakeChatbotResponse()

    monkeypatch.setattr(
        "app.api.v1.endpoints.admin_rag.httpx.AsyncClient",
        FakeAsyncClient,
    )

    login = await client.post(
        "/api/v1/auth/login",
        json={
            "firebase_uid": "upload_uid_1",
            "email": "upload@example.com",
            "is_active": True,
        },
    )
    assert login.status_code == 200
    headers = {"Authorization": "Bearer upload_uid_1"}

    response = await client.post(
        "/api/v1/admin/rag/documents/upload",
        headers=headers,
        files={"files": ("tiny.pdf", b"%PDF-1.4 tiny", "application/pdf")},
    )
    assert response.status_code == 200
    assert captured["timeout"] == pytest.approx(600.0)
    assert str(captured["url"]).endswith("/admin/documents/upload")


def test_upload_timeout_default_is_independent_of_chat_timeout(monkeypatch):
    monkeypatch.delenv("CHATBOT_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("CHATBOT_UPLOAD_TIMEOUT_SECONDS", raising=False)
    get_settings.cache_clear()
    settings = Settings(_env_file=None)
    assert settings.chatbot_timeout_seconds == 120.0
    assert settings.chatbot_upload_timeout_seconds == 600.0

    chat_only = Settings(_env_file=None, chatbot_timeout_seconds=30.0)
    assert chat_only.chatbot_timeout_seconds == 30.0
    assert chat_only.chatbot_upload_timeout_seconds == 600.0
