from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any, Dict
from app.models.ai import SenderType, OptimizationType

class AIMessageResponse(BaseModel):
    message_id: UUID
    conversation_id: UUID
    sender: SenderType
    content_encrypted: str # In real app, decrypt before sending or send encrypted if client handles it
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AIConversationResponse(BaseModel):
    conversation_id: UUID
    is_private: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ChatMessageCreate(BaseModel):
    content: str

class AIFeedbackCreate(BaseModel):
    user_action: str # 'ACCEPTED', 'IGNORED'
    outcome_metric: Optional[Dict[str, Any]] = None

class AIInsightResponse(BaseModel):
    optimization_id: UUID
    type: OptimizationType
    predicted_value: float
    reasoning: str
    model_config = ConfigDict(from_attributes=True)
