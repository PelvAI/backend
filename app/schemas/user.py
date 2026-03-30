from pydantic import BaseModel, ConfigDict, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from app.models.user import OrganizationType, RoleType, LinkStatus, DeletionStatus

# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    is_active: Optional[bool] = True

class UserCreate(UserBase):
    firebase_uid: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    user_id: UUID
    firebase_uid: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Profile Schemas ---
class ProfileBase(BaseModel):
    nickname: Optional[str] = None
    timezone: Optional[str] = "UTC"
    preferred_language: Optional[str] = "es"
    weight: Optional[float] = None
    height: Optional[float] = None
    birth_date: Optional[datetime] = None
    gender: Optional[str] = None
    notifications_enabled: Optional[bool] = True
    dark_mode: Optional[bool] = False
    
    # Clinical Dates (Phase 14)
    due_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    last_period_date: Optional[datetime] = None

class ProfileCreate(ProfileBase):
    pass

class ProfileUpdate(ProfileBase):
    avatar_storage_path: Optional[str] = None

class ProfileResponse(ProfileBase):
    profile_id: UUID
    user_id: UUID
    avatar_storage_path: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# --- Organization Schemas ---
class OrganizationBase(BaseModel):
    name: str
    type: OrganizationType

class OrganizationResponse(OrganizationBase):
    organization_id: UUID
    logo_storage_path: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# --- Affiliation Schemas ---
class AffiliationResponse(BaseModel):
    affiliation_id: UUID
    organization: OrganizationResponse
    role: RoleType
    model_config = ConfigDict(from_attributes=True)
