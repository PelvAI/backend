from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.services.clinical_context import _pregnancy_week, _postpartum_weeks


def test_pregnancy_week_from_lmp():
    profile = SimpleNamespace(
        last_period_date=datetime(2026, 1, 1),
        due_date=None,
    )
    now = datetime(2026, 3, 26)  # ~12 semanas
    assert _pregnancy_week(profile, now) == 12


def test_pregnancy_week_from_due_date():
    # due_date = LMP + 280d; LMP = 2026-01-01 → due = 2026-10-08
    profile = SimpleNamespace(
        last_period_date=None,
        due_date=datetime(2026, 10, 8),
    )
    now = datetime(2026, 3, 26)
    assert _pregnancy_week(profile, now) == 12


def test_pregnancy_week_none_without_dates():
    profile = SimpleNamespace(last_period_date=None, due_date=None)
    assert _pregnancy_week(profile, datetime(2026, 3, 26)) is None


def test_postpartum_weeks():
    profile = SimpleNamespace(delivery_date=datetime(2026, 1, 1))
    now = datetime(2026, 2, 12)  # 42 days → 6 weeks
    assert _postpartum_weeks(profile, now) == 6


@pytest.mark.asyncio
async def test_clinical_context_no_pii(db_session):
    from app.models.user import User, Profile
    from app.services.clinical_context import build_clinical_context

    user = User(
        user_id=uuid4(),
        firebase_uid="ctx_test_uid",
        email="secret@example.com",
        is_active=True,
    )
    profile = Profile(
        profile_id=uuid4(),
        user_id=user.user_id,
        nickname="SecretNick",
        preferred_language="es",
        last_period_date=datetime(2026, 1, 1),
    )
    db_session.add(user)
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(user)

    ctx = await build_clinical_context(db_session, user)
    forbidden = {"email", "nickname", "firebase_uid", "user_id", "profile_id"}
    assert forbidden.isdisjoint(ctx.keys())
    assert "schema_version" in ctx
    assert ctx["preferred_language"] == "es"
    assert "pregnancy_week" in ctx


@pytest.mark.asyncio
async def test_chatbot_client_chat_ok(monkeypatch):
    from app.core.config import get_settings
    from app.services.chatbot_client import ChatbotClient

    get_settings.cache_clear()
    monkeypatch.setenv("CHATBOT_SERVICE_TOKEN", "test-token-32chars-minimum-xxxxx")
    monkeypatch.setenv("CHATBOT_BASE_URL", "http://chatbot.test")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization", "").startswith("Bearer ")
        assert request.url.path == "/chat"
        return httpx.Response(
            200,
            json={
                "response": "hola",
                "session_id": "x",
                "evidence_quality": "ok",
                "sources_count": 1,
                "synthesis_duration_ms": 10,
            },
        )

    transport = httpx.MockTransport(handler)

    class _Client(ChatbotClient):
        async def chat(self, payload):
            timeout = self._settings.chatbot_timeout_seconds
            async with httpx.AsyncClient(transport=transport, timeout=timeout) as client:
                r = await client.post(
                    self._url("/chat"),
                    headers=self._headers(),
                    json=payload,
                )
            if r.status_code >= 400:
                from fastapi import HTTPException

                raise HTTPException(status_code=502, detail=f"Chatbot erro {r.status_code}")
            return r.json()

    bot = await _Client().chat({"query": "hola", "session_id": "s1"})
    assert bot["response"] == "hola"
    assert bot["evidence_quality"] == "ok"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_chatbot_client_requires_token(monkeypatch):
    from fastapi import HTTPException
    from app.core.config import get_settings
    from app.services.chatbot_client import ChatbotClient

    get_settings.cache_clear()
    monkeypatch.setenv("CHATBOT_SERVICE_TOKEN", "")
    get_settings.cache_clear()

    with pytest.raises(HTTPException) as exc:
        ChatbotClient()._headers()
    assert exc.value.status_code == 500
    get_settings.cache_clear()
