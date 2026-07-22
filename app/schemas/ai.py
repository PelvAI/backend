from pydantic import BaseModel, ConfigDict, model_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any, Dict
from app.models.ai import SenderType, OptimizationType


class AIMessageResponse(BaseModel):
    message_id: UUID
    conversation_id: UUID
    sender: SenderType
    content_encrypted: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AdminAIMessageResponse(BaseModel):
    message_id: UUID
    conversation_id: UUID
    sender: SenderType
    content_encrypted: str
    created_at: Optional[datetime] = None
    meta: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(from_attributes=True)


class AIConversationResponse(BaseModel):
    conversation_id: UUID
    is_private: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ChatMessageCreate(BaseModel):
    content: Optional[str] = None
    message: Optional[str] = None

    @model_validator(mode="after")
    def require_text(self):
        if not (self.content or self.message):
            raise ValueError("content required")
        return self

    def text(self) -> str:
        return (self.content or self.message or "").strip()


class AIFeedbackCreate(BaseModel):
    user_action: str  # 'ACCEPTED' | 'REJECTED' | 'IGNORED'
    outcome_metric: Optional[Dict[str, Any]] = None


class AIInsightResponse(BaseModel):
    optimization_id: UUID
    type: OptimizationType
    predicted_value: float
    reasoning: str
    model_config = ConfigDict(from_attributes=True)


class ActiveChatResponse(BaseModel):
    conversation_id: UUID


class AdminConversationItem(BaseModel):
    conversation_id: UUID
    user_id: Optional[UUID] = None
    user_email_hash: Optional[str] = None
    last_message_preview: Optional[str] = None
    last_message_at: Optional[datetime] = None
    message_count: int = 0


class AdminConversationListResponse(BaseModel):
    items: List[AdminConversationItem]
    total: int
