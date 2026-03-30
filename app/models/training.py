from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, Integer, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base
import uuid
from datetime import datetime
import enum

class AssignmentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    SKIPPED = "skipped"

class Exercise(Base):
    __tablename__ = "exercises"
    exercise_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    internal_code = Column(String, unique=True)
    video_path = Column(String)
    meta_data = Column(JSONB) # {duration: 300, category: "strength"}

class SessionTemplate(Base):
    __tablename__ = "session_templates"
    template_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String)
    exercises_config = Column(JSONB) # List of exercise_ids and reps

    assignments = relationship("UserAssignment", back_populates="template")

class UserAssignment(Base):
    __tablename__ = "user_daily_assignments"
    assignment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    template_id = Column(UUID(as_uuid=True), ForeignKey("session_templates.template_id"))
    date = Column(Date)
    status = Column(Enum(AssignmentStatus), default=AssignmentStatus.PENDING)

    user = relationship("User", back_populates="assignments")
    template = relationship("SessionTemplate", back_populates="assignments")
    performance = relationship("SessionPerformance", back_populates="assignment", uselist=False)

class SessionPerformance(Base):
    __tablename__ = "session_performance"
    performance_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("user_daily_assignments.assignment_id"))
    duration_actual = Column(Integer) # seconds
    perceived_exertion = Column(Integer) # 1-10
    pain_reported = Column(Integer) # 1-10

    assignment = relationship("UserAssignment", back_populates="performance")
