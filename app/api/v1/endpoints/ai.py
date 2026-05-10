from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.ai import AIConversation, AIMessage, SenderType, AIOptimization, OptimizationFeedback
from app.models.user import User
from app.schemas.ai import AIConversationResponse, AIMessageResponse, ChatMessageCreate, AIFeedbackCreate, AIInsightResponse
from app.api import deps
from uuid import UUID
from typing import List

router = APIRouter()

@router.post("/chat/new", response_model=AIConversationResponse)
async def start_new_conversation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Start a new chat conversation.
    """
    conv = AIConversation(user_id=current_user.user_id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv

@router.get("/chat/{conv_id}/messages", response_model=List[AIMessageResponse])
async def get_chat_messages(
    conv_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get messages for a conversation.
    """
    # Verify ownership
    result = await db.execute(select(AIConversation).where(AIConversation.conversation_id == conv_id))
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
    current_user: User = Depends(deps.get_current_user)
):
    """
    Send message to AI (and get response).
    """
    # Verify ownership
    result = await db.execute(select(AIConversation).where(AIConversation.conversation_id == conv_id))
    conv = result.scalars().first()
    if not conv or conv.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # 1. Save User Message
    user_msg = AIMessage(
        conversation_id=conv_id,
        sender=SenderType.USER,
        content_encrypted=msg_in.content # Encrypt in real app
    )
    db.add(user_msg)
    await db.commit()

    # 2. Trigger RAG / AI Response (Stub)
    ai_response_content = f"I received your message: '{msg_in.content}'. This is a stub response."
    
    ai_msg = AIMessage(
        conversation_id=conv_id,
        sender=SenderType.AI,
        content_encrypted=ai_response_content
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
    current_user: User = Depends(deps.get_current_user)
):
    """
    Submit feedback for an AI message (or optimization).
    """
    # For simplicity, assuming msg_id maps to an optimization or we create a feedback entry linked to something
    # The catalog says /feedback/{msg_id} but the model links to optimization_id. 
    # Let's assume this is for optimization feedback for now, or we need to link feedback to messages too.
    # Given the model `OptimizationFeedback` links to `optimization_id`, let's assume the ID passed is an optimization ID for now, 
    # or we'd need to update the model to support message feedback.
    # The catalog says "Usuario califica respuesta... para optimization_feedback".
    # I'll implement it as creating a feedback record.
    
    # Stub implementation
    return {"message": "Feedback received"}

@router.get("/insights", response_model=List[AIInsightResponse])
async def get_ai_insights(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get proactive AI insights/optimizations.
    """
    result = await db.execute(
        select(AIOptimization)
        .where(AIOptimization.user_id == current_user.user_id)
        .order_by(AIOptimization.created_at.desc())
    )
    return result.scalars().all()
