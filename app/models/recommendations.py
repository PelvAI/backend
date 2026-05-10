from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base
import uuid
from datetime import datetime
import enum

class RuleActionType(str, enum.Enum):
    ASSIGN_TRAINING = "assign_training"
    SEND_EMAIL = "send_email"
    UNLOCK_CONTENT = "unlock_content"

class RecommendationRule(Base):
    """
    Defines rules for the recommendation engine.
    Example: If ICIQ Score > 8, Assign "Recovery Plan".
    """
    __tablename__ = "recommendation_rules"
    
    rule_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String)
    description = Column(String)
    is_active = Column(Boolean, default=True)
    
    # Logic
    condition_expression = Column(Text) # e.g. "score >= 8" (SimpleEval compatible)
    target_form_code = Column(String, nullable=True) # Optional: Only apply for specific form code (e.g. "ICIQ-SF")
    
    # Action
    action_type = Column(Enum(RuleActionType))
    target_id = Column(UUID(as_uuid=True), nullable=True) # ID of template, content, etc.
    action_config = Column(JSONB, nullable=True) # Extra params
    
    priority = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
