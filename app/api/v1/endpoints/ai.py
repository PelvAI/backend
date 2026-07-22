import logging
from uuid import UUID, uuid4
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.db.session import get_db
from app.models.ai import AIConversation, AIMessage, SenderType, AIOptimization
from app.models.user import User
from app.schemas.ai import (
    AIConversationResponse,
    AIMessageResponse,
    ChatMessageCreate,
    AIFeedbackCreate,
    AIInsightResponse,
    ActiveChatResponse,
)
from app.api import deps
from app.services.chatbot_client import ChatbotClient
from app.services.clinical_context import build_clinical_context
from app.core.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat/new", response_model=AIConversationResponse)
async def start_new_conversation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Start a new chat conversation."""
    conv = AIConversation(user_id=current_user.user_id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.get("/chat/active", response_model=ActiveChatResponse)
async def get_active_conversation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Return the most recent conversation for the current user, or 404."""
    result = await db.execute(
        select(AIConversation)
        .where(AIConversation.user_id == current_user.user_id)
        .order_by(desc(AIConversation.created_at))
        .limit(1)
    )
    conv = result.scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="No active conversation")
    return ActiveChatResponse(conversation_id=conv.conversation_id)


@router.get("/chat/{conv_id}/messages", response_model=List[AIMessageResponse])
async def get_chat_messages(
    conv_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Get messages for a conversation."""
    result = await db.execute(
        select(AIConversation).where(AIConversation.conversation_id == conv_id)
    )
    conv = result.scalars().first()
    if not conv or conv.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(AIMessage)
        .where(AIMessage.conversation_id == conv_id)
        .order_by(AIMessage.created_at)
    )
    return result.scalars().all()


@router.post("/chat/{conv_id}/send", response_model=AIMessageResponse)
async def send_message(
    conv_id: UUID,
    msg_in: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Send message to AI via chatbot proxy and persist response."""
    result = await db.execute(
        select(AIConversation).where(AIConversation.conversation_id == conv_id)
    )
    conv = result.scalars().first()
    if not conv or conv.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    content = msg_in.text()
    if not content:
        raise HTTPException(status_code=422, detail="content required")

    settings = get_settings()
    correlation_id = str(uuid4())

    # Histórico sem a mensagem actual (ainda não commitada)
    clinical_context = await build_clinical_context(
        db, current_user, conversation_id=conv_id
    )

    user_msg = AIMessage(
        conversation_id=conv_id,
        sender=SenderType.USER,
        content_encrypted=content,
    )
    db.add(user_msg)
    await db.commit()

    payload = {
        "query": content,
        "session_id": str(conv_id),
        "correlation_id": correlation_id,
        "clinical_context": clinical_context,
    }

    logger.info(
        "chat_send",
        extra={
            "conversation_id": str(conv_id),
            "correlation_id": correlation_id,
            "query_chars": len(content),
        },
    )

    rag_meta: dict = {"correlation_id": correlation_id}
    try:
        bot = await ChatbotClient().chat(payload)
        ai_response_content = bot.get("response") or ""
        rag_meta.update(
            {
                "evidence_quality": bot.get("evidence_quality"),
                "sources_count": bot.get("sources_count"),
                "source_labels": bot.get("source_labels"),
                "synthesis_duration_ms": bot.get("synthesis_duration_ms"),
            }
        )
    except HTTPException:
        if settings.chatbot_required:
            raise
        ai_response_content = (
            "El asistente no está disponible en este momento. "
            "Inténtalo de nuevo más tarde."
        )
        rag_meta["fallback"] = True

    if not ai_response_content.strip():
        ai_response_content = "No pude generar una respuesta. Inténtalo de nuevo."

    ai_msg = AIMessage(
        conversation_id=conv_id,
        sender=SenderType.AI,
        content_encrypted=ai_response_content,
        meta=rag_meta,
    )
    db.add(ai_msg)
    await db.commit()
    await db.refresh(ai_msg)
    return ai_msg


@router.post("/feedback/{msg_id}")
async def submit_feedback(
    msg_id: UUID,
    feedback_in: AIFeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Store user feedback on an AI message (meta.feedback)."""
    result = await db.execute(select(AIMessage).where(AIMessage.message_id == msg_id))
    msg = result.scalars().first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    conv_result = await db.execute(
        select(AIConversation).where(
            AIConversation.conversation_id == msg.conversation_id
        )
    )
    conv = conv_result.scalars().first()
    if not conv or conv.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Message not found")

    action = (feedback_in.user_action or "").upper()
    if action not in {"ACCEPTED", "REJECTED", "IGNORED"}:
        raise HTTPException(status_code=422, detail="Invalid user_action")

    meta = dict(msg.meta or {})
    meta["feedback"] = {
        "user_action": action,
        "outcome_metric": feedback_in.outcome_metric,
    }
    msg.meta = meta
    await db.commit()
    return {"ok": True}


@router.get("/insights", response_model=List[AIInsightResponse])
async def get_ai_insights(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Get proactive AI insights/optimizations."""
    result = await db.execute(
        select(AIOptimization)
        .where(AIOptimization.user_id == current_user.user_id)
        .order_by(desc(AIOptimization.created_at))
    )
    return result.scalars().all()
