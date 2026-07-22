import hashlib
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models.ai import AIConversation, AIMessage
from app.models.user import User
from app.schemas.ai import (
    AdminAIMessageResponse,
    AdminConversationItem,
    AdminConversationListResponse,
)

router = APIRouter()


def _email_hash(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    return hashlib.sha256(email.encode("utf-8")).hexdigest()[:12]


@router.get("/chat/conversations", response_model=AdminConversationListResponse)
async def list_conversations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """List patient conversations for the staff Monitor (BD Alma)."""
    total_result = await db.execute(select(func.count()).select_from(AIConversation))
    total = int(total_result.scalar() or 0)

    result = await db.execute(
        select(AIConversation)
        .options(selectinload(AIConversation.user))
        .order_by(AIConversation.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    conversations = result.scalars().all()

    items: list[AdminConversationItem] = []
    for conv in conversations:
        msg_count_result = await db.execute(
            select(func.count())
            .select_from(AIMessage)
            .where(AIMessage.conversation_id == conv.conversation_id)
        )
        message_count = int(msg_count_result.scalar() or 0)

        last_msg_result = await db.execute(
            select(AIMessage)
            .where(AIMessage.conversation_id == conv.conversation_id)
            .order_by(AIMessage.created_at.desc())
            .limit(1)
        )
        last_msg = last_msg_result.scalars().first()
        preview = None
        last_at = conv.created_at
        if last_msg:
            preview = (last_msg.content_encrypted or "")[:120]
            last_at = last_msg.created_at

        email = conv.user.email if conv.user else None
        items.append(
            AdminConversationItem(
                conversation_id=conv.conversation_id,
                user_id=conv.user_id,
                user_email_hash=_email_hash(email),
                last_message_preview=preview,
                last_message_at=last_at,
                message_count=message_count,
            )
        )

    return AdminConversationListResponse(items=items, total=total)


@router.get(
    "/chat/conversations/{conv_id}/messages",
    response_model=list[AdminAIMessageResponse],
)
async def get_conversation_messages(
    conv_id: UUID,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Messages for Monitor — includes RAG meta when present."""
    result = await db.execute(
        select(AIConversation).where(AIConversation.conversation_id == conv_id)
    )
    conv = result.scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs = await db.execute(
        select(AIMessage)
        .where(AIMessage.conversation_id == conv_id)
        .order_by(AIMessage.created_at)
    )
    return msgs.scalars().all()
