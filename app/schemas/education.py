from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional
from app.models.education import EducationType

class EducationModuleBase(BaseModel):
    title: str
    content: str
    type: EducationType
    category: str
    thumbnail_url: Optional[str] = None
    is_active: Optional[bool] = True

class EducationModuleCreate(EducationModuleBase):
    pass

class EducationModuleResponse(EducationModuleBase):
    module_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
