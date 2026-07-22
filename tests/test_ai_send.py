import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_admin_rag_requires_auth(client, monkeypatch):
    """Unknown Bearer → 401 on admin RAG."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    get_settings.cache_clear()

    response = await client.get(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": "Bearer unknown_uid_xyz"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_send_message_calls_chatbot(client, monkeypatch):
    monkeypatch.setenv("CHATBOT_SERVICE_TOKEN", "test-token-32chars-minimum-xxxxx")
    monkeypatch.setenv("CHATBOT_REQUIRED", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    get_settings.cache_clear()

    login = await client.post(
        "/api/v1/auth/login",
        json={
            "firebase_uid": "chat_uid_1",
            "email": "chat@example.com",
            "is_active": True,
        },
    )
    assert login.status_code == 200
    headers = {"Authorization": "Bearer chat_uid_1"}

    conv_res = await client.post("/api/v1/ai/chat/new", headers=headers)
    assert conv_res.status_code == 200
    conv_id = conv_res.json()["conversation_id"]

    async def fake_chat(self, payload):
        assert payload["query"] == "hola"
        assert payload["session_id"] == conv_id
        assert "clinical_context" in payload
        assert payload["clinical_context"]["schema_version"] == "v1"
        return {
            "response": "respuesta real del bot",
            "session_id": conv_id,
            "evidence_quality": "ok",
            "sources_count": 2,
            "source_labels": ["guia.pdf"],
            "synthesis_duration_ms": 42,
        }

    monkeypatch.setattr(
        "app.api.v1.endpoints.ai.ChatbotClient.chat",
        fake_chat,
    )

    send = await client.post(
        f"/api/v1/ai/chat/{conv_id}/send",
        headers=headers,
        json={"content": "hola"},
    )
    assert send.status_code == 200
    data = send.json()
    assert data["content_encrypted"] == "respuesta real del bot"
    assert data["sender"] == "ai"


@pytest.mark.asyncio
async def test_send_message_accepts_message_alias(client, monkeypatch):
    monkeypatch.setenv("CHATBOT_SERVICE_TOKEN", "tok")
    monkeypatch.setenv("CHATBOT_REQUIRED", "false")
    get_settings.cache_clear()

    await client.post(
        "/api/v1/auth/login",
        json={
            "firebase_uid": "alias_uid",
            "email": "alias@example.com",
            "is_active": True,
        },
    )
    headers = {"Authorization": "Bearer alias_uid"}
    conv_id = (
        await client.post("/api/v1/ai/chat/new", headers=headers)
    ).json()["conversation_id"]

    async def fake_chat(self, payload):
        assert payload["query"] == "alias body"
        return {"response": "ok", "session_id": conv_id}

    monkeypatch.setattr("app.api.v1.endpoints.ai.ChatbotClient.chat", fake_chat)

    send = await client.post(
        f"/api/v1/ai/chat/{conv_id}/send",
        headers=headers,
        json={"message": "alias body"},
    )
    assert send.status_code == 200


@pytest.mark.asyncio
async def test_admin_chat_monitor_lists_conversations(client, db_session):
    await client.post(
        "/api/v1/auth/login",
        json={
            "firebase_uid": "admin_mon",
            "email": "admin@example.com",
            "is_active": True,
        },
    )
    headers = {"Authorization": "Bearer admin_mon"}
    conv = await client.post("/api/v1/ai/chat/new", headers=headers)
    conv_id = conv.json()["conversation_id"]

    list_res = await client.get("/api/v1/admin/chat/conversations", headers=headers)
    assert list_res.status_code == 200
    body = list_res.json()
    assert body["total"] >= 1
    ids = [i["conversation_id"] for i in body["items"]]
    assert conv_id in ids
    for item in body["items"]:
        if item["conversation_id"] == conv_id:
            assert item["user_email_hash"]
            assert "@" not in item["user_email_hash"]


@pytest.mark.asyncio
async def test_feedback_on_ai_message(client, monkeypatch):
    monkeypatch.setenv("CHATBOT_SERVICE_TOKEN", "tok")
    monkeypatch.setenv("CHATBOT_REQUIRED", "false")
    get_settings.cache_clear()

    await client.post(
        "/api/v1/auth/login",
        json={
            "firebase_uid": "fb_uid",
            "email": "fb@example.com",
            "is_active": True,
        },
    )
    headers = {"Authorization": "Bearer fb_uid"}
    conv_id = (
        await client.post("/api/v1/ai/chat/new", headers=headers)
    ).json()["conversation_id"]

    async def fake_chat(self, payload):
        return {"response": "ok", "session_id": conv_id}

    monkeypatch.setattr("app.api.v1.endpoints.ai.ChatbotClient.chat", fake_chat)

    send = await client.post(
        f"/api/v1/ai/chat/{conv_id}/send",
        headers=headers,
        json={"content": "hola"},
    )
    msg_id = send.json()["message_id"]

    fb = await client.post(
        f"/api/v1/ai/feedback/{msg_id}",
        headers=headers,
        json={"user_action": "ACCEPTED"},
    )
    assert fb.status_code == 200
    assert fb.json()["ok"] is True
