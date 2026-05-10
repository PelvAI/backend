from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.user import User, Profile
from app.schemas.user import ProfileResponse, ProfileUpdate
from app.api import deps
from uuid import UUID

router = APIRouter()

@router.get("/me", response_model=ProfileResponse)
async def read_profile_me(
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user profile.
    """
    result = await db.execute(select(Profile).where(Profile.user_id == current_user.user_id))
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile

@router.patch("/me", response_model=ProfileResponse)
async def update_profile_me(
    profile_in: ProfileUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current user profile.
    """
    result = await db.execute(select(Profile).where(Profile.user_id == current_user.user_id))
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    update_data = profile_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return profile

@router.post("/me/avatar")
async def upload_avatar(
    current_user: User = Depends(deps.get_current_user),
):
    """
    Upload avatar. (Stub implementation)
    """
    # In a real app, handle file upload to S3 here
    return {"avatar_storage_path": "avatars/stub_avatar.png"}

@router.get("/{profile_id}/public", response_model=ProfileResponse)
async def read_public_profile(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get public profile by ID.
    """
    result = await db.execute(select(Profile).where(Profile.profile_id == profile_id))
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile
