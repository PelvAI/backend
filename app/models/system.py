from sqlalchemy import Column, String, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.session import Base
import uuid

class SystemSetting(Base):
    __tablename__ = "system_settings"
    setting_key = Column(String, primary_key=True)
    value = Column(JSONB)

class Translation(Base):
    __tablename__ = "content_translations"
    translation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String)
    language_code = Column(String)
    text = Column(String)
