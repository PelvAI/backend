from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, Integer, Text, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base
import uuid
from datetime import datetime
import enum

class SenderType(str, enum.Enum):
    USER = "user"
    AI = "ai"
    SYSTEM = "system"

class OptimizationType(str, enum.Enum):
    DIFFICULTY_ADJUSTMENT = "difficulty_adjustment"
    CONTENT_RECOMMENDATION = "content_recommendation"
    RISK_ALERT = "risk_alert"

class UserAction(str, enum.Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IGNORED = "ignored"

class AIConversation(Base):
    __tablename__ = "ai_conversations"
    conversation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    is_private = Column(Boolean, default=True)

    user = relationship("app.models.user.User", backref="conversations")
    messages = relationship("AIMessage", back_populates="conversation")

class AIMessage(Base):
    __tablename__ = "ai_messages"
    message_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("ai_conversations.conversation_id"))
    sender = Column(Enum(SenderType))
    content_encrypted = Column(Text) # In a real app, this should be encrypted

    conversation = relationship("AIConversation", back_populates="messages")

class AIRagSource(Base):
    __tablename__ = "ai_rag_sources"
    source_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String)
    vector_id = Column(String)
    citation_text = Column(Text)

class AIOptimization(Base):
    __tablename__ = "ai_optimizations"
    optimization_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    type = Column(Enum(OptimizationType))
    predicted_value = Column(Float)
    reasoning = Column(Text)

    user = relationship("app.models.user.User", backref="optimizations")
    feedback = relationship("OptimizationFeedback", back_populates="optimization", uselist=False)

class OptimizationFeedback(Base):
    __tablename__ = "optimization_feedback"
    feedback_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    optimization_id = Column(UUID(as_uuid=True), ForeignKey("ai_optimizations.optimization_id"))
    user_action = Column(Enum(UserAction))
    outcome_metric = Column(JSONB)

    optimization = relationship("AIOptimization", back_populates="feedback")
