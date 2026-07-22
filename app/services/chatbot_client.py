from __future__ import annotations

from typing import Any, Optional

import httpx
from fastapi import HTTPException

from app.core.config import get_settings


class ChatbotClient:
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self._settings = get_settings()
        self._client = client

    def _headers(self) -> dict[str, str]:
        token = self._settings.chatbot_service_token
        if not token:
            raise HTTPException(
                status_code=500,
                detail="CHATBOT_SERVICE_TOKEN não configurado",
            )
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _url(self, path: str) -> str:
        base = self._settings.chatbot_base_url.rstrip("/")
        return f"{base}{path}"

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(self._url("/health"))
            r.raise_for_status()
            return r.json()

    async def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /chat no PelvAI com clinical_context."""
        timeout = self._settings.chatbot_timeout_seconds
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(
                    self._url("/chat"),
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Chatbot indisponível: {exc}",
            ) from exc

        if r.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Chatbot erro {r.status_code}",
            )
        return r.json()

    async def proxy(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        content: bytes | None = None,
        headers_extra: dict | None = None,
        params: dict | None = None,
        files: Any = None,
    ) -> httpx.Response:
        """Proxy genérico para /admin/* do chatbot (RAG)."""
        headers = self._headers()
        if files is not None:
            headers.pop("Content-Type", None)
        if headers_extra:
            headers.update(headers_extra)

        timeout = self._settings.chatbot_timeout_seconds
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.request(
                method,
                self._url(path),
                headers=headers,
                json=json_body,
                content=content,
                params=params,
                files=files,
            )
