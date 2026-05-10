from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.system import SystemSetting, Translation
from app.models.user import User
from app.schemas.system import SystemConfigResponse, TranslationResponse, DeviceTokenCreate
from app.api import deps
from typing import List

router = APIRouter()

@router.get("/config", response_model=List[SystemConfigResponse])
async def get_system_config(
    db: AsyncSession = Depends(get_db),
    # Config might be public or require auth, assuming public for feature flags often, but let's require auth for consistency unless specified
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get system configuration (feature flags).
    """
    result = await db.execute(select(SystemSetting))
    settings = result.scalars().all()
    
    response = []
    for s in settings:
        response.append(SystemConfigResponse(key=s.setting_key, value=s.value))
    return response

@router.get("/translations", response_model=List[TranslationResponse])
async def get_translations(
    language: str = "es",
    db: AsyncSession = Depends(get_db),
):
    """
    Get translations for a specific language.
    """
    result = await db.execute(
        select(Translation)
        .where(Translation.language_code == language)
    )
    return result.scalars().all()

@router.post("/device-token")
async def register_device_token(
    token_in: DeviceTokenCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Register device token for push notifications. (Stub)
    """
    # In real app: Save to user_devices table
    return {"message": "Token registered"}
