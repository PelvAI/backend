from typing import Generator, Optional
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.user import User

async def get_current_user(
    auth_header: Optional[str] = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Mock authentication for development.
    In production, this would verify the Firebase ID Token.
    
    DEV MODE: If no token is provided, defaults to 'test_uid_123'.
    """
    if not auth_header:
        # print("DEBUG: No Authorization header received. Using DEV DEFAULT: test_uid_123")
        token = "test_uid_123"
    else:
        token = auth_header.replace("Bearer ", "")
        # print(f"DEBUG: Received token/uid: {token}")
    
    # In a real app, verify token here.
    # For dev, we treat the token as the firebase_uid directly.
    
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User)
        .where(User.firebase_uid == token)
        .options(selectinload(User.profile))
    )
    user = result.scalars().first()
    
    if not user:
        # print(f"DEBUG: User {token} not found in DB")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    # print(f"DEBUG: User found: {user.email} (ID: {user.user_id})")
    return user

async def get_current_admin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Verify that the current user has admin privileges.
    For MVP, we might allow any authenticated user or check a specific flag/table.
    """
    # TODO: Implement robust RBAC checking against Affiliation table for 'admin' role.
    # For now, we assume if you can login you are admin (DEV MODE only) or check is_active.
    if not current_user.is_active:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user
