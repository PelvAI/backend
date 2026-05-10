from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, Integer, JSON, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base
import uuid
from datetime import datetime
import enum

class User(Base):
    __tablename__ = "users"
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firebase_uid = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    profile = relationship("Profile", back_populates="user", uselist=False)
    submissions = relationship("UserSubmission", back_populates="user")
    assignments = relationship("UserAssignment", back_populates="user")
    wallet = relationship("Wallet", back_populates="user", uselist=False)
    inventory = relationship("UserInventory", back_populates="user")
    streak = relationship("UserStreak", back_populates="user", uselist=False)

class Profile(Base):
    __tablename__ = "profiles"
    profile_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    nickname = Column(String)
    avatar_storage_path = Column(String)
    timezone = Column(String)
    preferred_language = Column(String)
    
    # Biometrics
    weight = Column(Float, nullable=True) # in kg
    height = Column(Float, nullable=True) # in cm
    birth_date = Column(DateTime, nullable=True)
    gender = Column(String, nullable=True)
    
    # Clinical/Temporal Dates (Phase 14)
    due_date = Column(DateTime, nullable=True)          # Estimated delivery date
    delivery_date = Column(DateTime, nullable=True)     # Actual delivery date
    last_period_date = Column(DateTime, nullable=True)  # Last menstrual period

    # Settings
    notifications_enabled = Column(Boolean, default=True)
    dark_mode = Column(Boolean, default=False)

    user = relationship("User", back_populates="profile")
    affiliations = relationship("Affiliation", back_populates="profile")
    targets = relationship("Target", secondary="profile_targets")

class OrganizationType(str, enum.Enum):
    CLINIC = "clinic"
    GYM = "gym"
    COMPANY = "company"

class Organization(Base):
    __tablename__ = "organizations"
    organization_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String)
    type = Column(Enum(OrganizationType))
    logo_storage_path = Column(String)

    teams = relationship("Team", back_populates="organization")
    affiliations = relationship("Affiliation", back_populates="organization")

class Team(Base):
    __tablename__ = "teams"
    team_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.organization_id"))
    name = Column(String)

    organization = relationship("Organization", back_populates="teams")
    affiliations = relationship("Affiliation", back_populates="team")

class RoleType(str, enum.Enum):
    ADMIN = "admin"
    MEDIC = "medic"
    TRAINER = "trainer"
    MEMBER = "member"

class Affiliation(Base):
    __tablename__ = "affiliations"
    affiliation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.profile_id"))
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.organization_id"))
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.team_id"), nullable=True)
    role = Column(Enum(RoleType))

    profile = relationship("Profile", back_populates="affiliations")
    organization = relationship("Organization", back_populates="affiliations")
    team = relationship("Team", back_populates="affiliations")

class LinkStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"

class ProfessionalLink(Base):
    __tablename__ = "professional_links"
    link_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    medic_profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.profile_id"))
    patient_profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.profile_id"))
    security_scope = Column(JSONB)
    status = Column(Enum(LinkStatus))

class AuditLog(Base):
    __tablename__ = "audit_access_logs"
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    actor_id = Column(UUID(as_uuid=True))
    resource_accessed = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String)

class DeletionStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"

class DeletionRequest(Base):
    __tablename__ = "account_deletion_requests"
    request_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    request_date = Column(DateTime, default=datetime.utcnow)
    scheduled_deletion_date = Column(DateTime)
    status = Column(Enum(DeletionStatus))
