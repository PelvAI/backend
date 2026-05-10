from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.session import Base
import uuid
from datetime import datetime
import enum

class NodeType(str, enum.Enum):
    LESSON = "lesson"
    QUIZ = "quiz"
    CHALLENGE = "challenge"
    REWARD = "reward"

class ReferenceType(str, enum.Enum):
    VIDEO = "video"
    ARTICLE = "article"
    EXERCISE = "exercise"
    FORM = "form"

class LearningPath(Base):
    __tablename__ = "learning_paths"
    path_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name_key = Column(String)
    target_profile = Column(String) # e.g., "postpartum", "menopause"

    nodes = relationship("PathNode", back_populates="path")

class PathNode(Base):
    __tablename__ = "path_nodes"
    node_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    path_id = Column(UUID(as_uuid=True), ForeignKey("learning_paths.path_id"))
    coordinate_x = Column(Integer)
    coordinate_y = Column(Integer)
    type = Column(Enum(NodeType))

    path = relationship("LearningPath", back_populates="nodes")
    content = relationship("NodeContent", back_populates="node", uselist=False)
    requirements = relationship("NodeRequirement", foreign_keys="[NodeRequirement.node_id]", back_populates="node")
    user_progress = relationship("UserPathProgress", back_populates="node")

class NodeContent(Base):
    __tablename__ = "node_content"
    content_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id = Column(UUID(as_uuid=True), ForeignKey("path_nodes.node_id"))
    reference_id = Column(UUID(as_uuid=True)) # ID of the video, article, etc.
    reference_type = Column(Enum(ReferenceType))

    node = relationship("PathNode", back_populates="content")

class NodeRequirement(Base):
    __tablename__ = "node_requirements"
    requirement_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id = Column(UUID(as_uuid=True), ForeignKey("path_nodes.node_id"))
    required_node_id = Column(UUID(as_uuid=True), ForeignKey("path_nodes.node_id"))
    min_score = Column(Integer)

    node = relationship("PathNode", foreign_keys=[node_id], back_populates="requirements")
    required_node = relationship("PathNode", foreign_keys=[required_node_id])

class UserPathProgress(Base):
    __tablename__ = "user_path_progress"
    progress_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    node_id = Column(UUID(as_uuid=True), ForeignKey("path_nodes.node_id"))
    stars_earned = Column(Integer)
    completed_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("app.models.user.User", backref="path_progress")
    node = relationship("PathNode", back_populates="user_progress")
