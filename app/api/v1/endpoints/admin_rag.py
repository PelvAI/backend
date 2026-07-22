from typing import Any, List

from fastapi import APIRouter, Depends, File, Response, UploadFile
import httpx

from app.api.deps import get_current_admin
from app.core.config import get_settings
from app.services.chatbot_client import ChatbotClient

router = APIRouter()


def _proxy_response(r: httpx.Response) -> Response:
    media = r.headers.get("content-type", "application/json")
    return Response(content=r.content, status_code=r.status_code, media_type=media)


@router.get("/rag/documents")
async def list_rag_documents(admin=Depends(get_current_admin)):
    client = ChatbotClient()
    r = await client.proxy("GET", "/admin/documents")
    return _proxy_response(r)


@router.post("/rag/documents/upload")
async def upload_rag_documents(
    admin=Depends(get_current_admin),
    files: List[UploadFile] = File(...),
):
    settings = get_settings()
    if not settings.chatbot_service_token:
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail="CHATBOT_SERVICE_TOKEN não configurado")

    multiparts = []
    for f in files:
        content = await f.read()
        multiparts.append(
            (
                "files",
                (f.filename, content, f.content_type or "application/octet-stream"),
            )
        )
    async with httpx.AsyncClient(timeout=settings.chatbot_timeout_seconds) as http:
        r = await http.post(
            f"{settings.chatbot_base_url.rstrip('/')}/admin/documents/upload",
            headers={"Authorization": f"Bearer {settings.chatbot_service_token}"},
            files=multiparts,
        )
    return _proxy_response(r)


@router.patch("/rag/documents/{doc_id}")
async def patch_rag_document(
    doc_id: int,
    body: dict[str, Any],
    admin=Depends(get_current_admin),
):
    client = ChatbotClient()
    r = await client.proxy("PATCH", f"/admin/documents/{doc_id}", json_body=body)
    return _proxy_response(r)


@router.delete("/rag/documents/{doc_id}")
async def delete_rag_document(doc_id: int, admin=Depends(get_current_admin)):
    client = ChatbotClient()
    r = await client.proxy("DELETE", f"/admin/documents/{doc_id}")
    return _proxy_response(r)


@router.get("/rag/reindex/status")
async def reindex_status(admin=Depends(get_current_admin)):
    client = ChatbotClient()
    r = await client.proxy("GET", "/admin/reindex/status")
    return _proxy_response(r)


@router.post("/rag/reindex/confirm")
async def reindex_confirm(
    admin=Depends(get_current_admin),
    sync: bool = False,
):
    client = ChatbotClient()
    r = await client.proxy(
        "POST",
        "/admin/reindex/confirm",
        params={"sync": "true" if sync else "false"},
    )
    return _proxy_response(r)


@router.get("/rag/analytics/summary")
async def rag_analytics_summary(admin=Depends(get_current_admin)):
    client = ChatbotClient()
    r = await client.proxy("GET", "/admin/analytics/summary")
    return _proxy_response(r)


@router.get("/rag/analytics/chunks")
async def rag_analytics_chunks(admin=Depends(get_current_admin)):
    client = ChatbotClient()
    r = await client.proxy("GET", "/admin/analytics/chunks")
    return _proxy_response(r)
