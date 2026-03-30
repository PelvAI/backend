from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any, Dict
from app.models.map import NodeType, ReferenceType

class NodeContentResponse(BaseModel):
    content_id: UUID
    reference_id: UUID
    reference_type: ReferenceType
    model_config = ConfigDict(from_attributes=True)

class PathNodeResponse(BaseModel):
    node_id: UUID
    path_id: UUID
    coordinate_x: int
    coordinate_y: int
    type: NodeType
    content: Optional[NodeContentResponse] = None
    model_config = ConfigDict(from_attributes=True)

class LearningPathResponse(BaseModel):
    path_id: UUID
    name_key: str
    target_profile: str
    model_config = ConfigDict(from_attributes=True)

class UserPathProgressResponse(BaseModel):
    progress_id: UUID
    node_id: UUID
    stars_earned: int
    completed_at: datetime
    model_config = ConfigDict(from_attributes=True)
