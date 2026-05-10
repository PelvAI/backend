from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import date
from typing import Optional, List, Dict, Any
from app.models.training import AssignmentStatus

class ExerciseResponse(BaseModel):
    exercise_id: UUID
    internal_code: str
    video_path: Optional[str] = None
    meta_data: Dict[str, Any]
    model_config = ConfigDict(from_attributes=True)

class SessionTemplateResponse(BaseModel):
    template_id: UUID
    name: str
    exercises_config: Dict[str, Any]
    model_config = ConfigDict(from_attributes=True)

class AssignmentResponse(BaseModel):
    assignment_id: UUID
    date: date
    status: AssignmentStatus
    template: SessionTemplateResponse
    model_config = ConfigDict(from_attributes=True)

class SessionCompletion(BaseModel):
    assignment_id: UUID
    duration_actual: int
    perceived_exertion: int
    pain_reported: int

class SessionProgress(BaseModel):
    exercise_id: UUID
    completed: bool
