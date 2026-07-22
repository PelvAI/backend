from typing import Optional

from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User, RoleType, Profile
from app.core.config import get_settings


async def get_current_user(
    auth_header: Optional[str] = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Mock authentication for development.
    In production, this would verify the Firebase ID Token.

    DEV MODE: If no token is provided, defaults to 'test_uid_123'.
    """
    if not auth_header:
        token = "test_uid_123"
    else:
        token = auth_header.replace("Bearer ", "")

    result = await db.execute(
        select(User)
        .where(User.firebase_uid == token)
        .options(selectinload(User.profile))
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


_ADMIN_ROLES = {RoleType.ADMIN, RoleType.MEDIC}


async def get_current_admin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Verify admin/medic privileges via Affiliation.
    In ENVIRONMENT=development, any active user is allowed (documented bypass).
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    settings = get_settings()
    if settings.environment == "development":
        return current_user

    result = await db.execute(
        select(Profile)
        .where(Profile.user_id == current_user.user_id)
        .options(selectinload(Profile.affiliations))
    )
    profile = result.scalars().first()

    roles = {a.role for a in (profile.affiliations if profile else [])}
    if not roles.intersection(_ADMIN_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
