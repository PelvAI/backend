from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.session import Base
import uuid
from datetime import datetime
import enum

class EducationType(str, enum.Enum):
    ARTICLE = "article"
    VIDEO = "video"
    TIP = "tip"

class EducationModule(Base):
    __tablename__ = "education_modules"
    module_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String)
    content = Column(Text) # Markdown or HTML content
    type = Column(Enum(EducationType))
    category = Column(String) # e.g., "Anatomy", "Lifestyle"
    thumbnail_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
