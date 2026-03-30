from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.user import User, Profile
from app.models.gamification import Wallet, Currency
from app.schemas.user import UserCreate, UserResponse
from app.api import deps

router = APIRouter()

@router.post("/login", response_model=UserResponse)
async def login(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Login or Register a user via Firebase UID.
    """
    # Check if user exists
    result = await db.execute(select(User).where(User.firebase_uid == user_in.firebase_uid))
    user = result.scalars().first()

    if not user:
        # Register new user
        user = User(
            firebase_uid=user_in.firebase_uid,
            email=user_in.email,
            is_active=True
        )
        db.add(user)
        await db.flush() # Get user_id

        # Create Profile
        profile = Profile(
            user_id=user.user_id,
            nickname=user_in.email.split("@")[0],
            timezone="UTC",
            preferred_language="es"
        )
        db.add(profile)

        # Create Wallet (Initialize with 0 XP)
        # We need to find the XP currency first, assuming seeded
        xp_currency = (await db.execute(select(Currency).where(Currency.code == "XP"))).scalars().first()
        if xp_currency:
             wallet = Wallet(user_id=user.user_id, currency_id=xp_currency.currency_id, balance=0)
             db.add(wallet)

        await db.commit()
        await db.refresh(user)
    
    return user

@router.post("/register", response_model=UserResponse)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user.
    """
    # Check if user exists
    result = await db.execute(select(User).where(User.firebase_uid == user_in.firebase_uid))
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists",
        )

    # Register new user
    user = User(
        firebase_uid=user_in.firebase_uid,
        email=user_in.email,
        is_active=True
    )
    db.add(user)
    await db.flush()

    # Create Profile
    profile = Profile(
        user_id=user.user_id,
        nickname=user_in.email.split("@")[0],
        timezone="UTC",
        preferred_language="es"
    )
    db.add(profile)

    # Create Wallet (Initialize with 0 XP)
    xp_currency = (await db.execute(select(Currency).where(Currency.code == "XP"))).scalars().first()
    if xp_currency:
            wallet = Wallet(user_id=user.user_id, currency_id=xp_currency.currency_id, balance=0)
            db.add(wallet)

    await db.commit()
    await db.refresh(user)
    return user

@router.post("/refresh")
async def refresh_token(
    current_user: User = Depends(deps.get_current_user),
):
    """
    Refresh access token. (Stub implementation)
    """
    return {"message": "Token refreshed"}

@router.post("/logout")
async def logout(
    current_user: User = Depends(deps.get_current_user),
):
    """
    Logout user. (Stub implementation)
    """
    return {"message": "Logged out"}

from app.models.user import DeletionRequest, DeletionStatus
from datetime import datetime, timedelta

@router.post("/delete-account")
async def delete_account(
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate account deletion (Right to be Forgotten).
    """
    # Soft delete user
    current_user.is_active = False
    
    # Create deletion request
    request = DeletionRequest(
        user_id=current_user.user_id,
        scheduled_deletion_date=datetime.utcnow() + timedelta(days=30),
        status=DeletionStatus.PENDING
    )
    db.add(request)
    await db.commit()
    
    return {"message": "Account deletion scheduled for 30 days from now"}

@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: User = Depends(deps.get_current_user),
):
    """
    Get current user.
    """
    return current_user
