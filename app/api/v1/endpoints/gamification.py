from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.models.user import User
from app.models.gamification import Wallet, Currency, Transaction, ShopItem, UserInventory, Season, UserStreak
from app.schemas.gamification import UserStats, WalletResponse, TransactionResponse, ShopItemResponse, UserInventoryResponse, SeasonResponse, LeaderboardEntry
from app.api import deps
from typing import List
from uuid import UUID

router = APIRouter()

@router.get("/stats", response_model=UserStats)
async def get_user_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get user gamification stats (XP, Streak, League).
    """
    # Get XP Wallet
    result = await db.execute(
        select(Wallet)
        .join(Currency)
        .where(Wallet.user_id == current_user.user_id)
        .where(Currency.code == "XP")
    )
    xp_wallet = result.scalars().first()
    xp = xp_wallet.balance if xp_wallet else 0
    
    # Calculate Level (Simple logic: 1 level every 100 XP)
    level = (xp // 100) + 1

    # Query Streak
    res_streak = await db.execute(select(UserStreak).where(UserStreak.user_id == current_user.user_id))
    streak_record = res_streak.scalars().first()
    current_streak = streak_record.current_streak if streak_record else 0

    return UserStats(
        xp=xp,
        streak=current_streak, 
        league="Diamante", # Mock
        league_position=12, # Mock
        wellness_index=72, # Mock
        level=level,
        program_week=1 # Mock
    )

@router.get("/wallet", response_model=List[WalletResponse])
async def get_wallet(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get wallet balance for all currencies.
    """
    result = await db.execute(
        select(Wallet)
        .options(selectinload(Wallet.currency))
        .where(Wallet.user_id == current_user.user_id)
    )
    wallets = result.scalars().all()
    
    response = []
    for w in wallets:
        response.append(WalletResponse(balance=w.balance, currency_code=w.currency.code))
        
    return response

@router.get("/wallet/history", response_model=List[TransactionResponse])
async def get_wallet_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get transaction history.
    """
    # Join Wallet to filter by user
    result = await db.execute(
        select(Transaction)
        .join(Wallet)
        .where(Wallet.user_id == current_user.user_id)
        .order_by(Transaction.created_at.desc())
    )
    return result.scalars().all()

@router.get("/shop/catalog", response_model=List[ShopItemResponse])
async def get_shop_catalog(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get items available in the shop.
    """
    result = await db.execute(select(ShopItem))
    return result.scalars().all()

@router.post("/shop/buy/{item_id}")
async def buy_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Buy an item. (Stub)
    """
    # Logic: Check balance, deduct cost, add to inventory
    return {"message": "Item purchased", "item_id": item_id}

@router.get("/inventory", response_model=List[UserInventoryResponse])
async def get_inventory(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get user inventory.
    """
    result = await db.execute(
        select(UserInventory)
        .where(UserInventory.user_id == current_user.user_id)
    )
    return result.scalars().all()

@router.post("/inventory/{item_id}/equip")
async def equip_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Equip an item. (Stub)
    """
    return {"message": "Item equipped", "item_id": item_id}

@router.get("/seasons/current", response_model=SeasonResponse)
async def get_current_season(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get current season info.
    """
    # Stub: Return first season or dummy
    result = await db.execute(select(Season))
    season = result.scalars().first()
    if not season:
        # Dummy
        from datetime import datetime, timedelta
        return SeasonResponse(
            season_id=UUID("00000000-0000-0000-0000-000000000000"),
            name="Pre-Season",
            end_date=datetime.utcnow() + timedelta(days=30)
        )
    return season

@router.get("/leaderboard/global", response_model=List[LeaderboardEntry])
async def get_global_leaderboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get global leaderboard. (Stub)
    """
    return [
        LeaderboardEntry(position=1, nickname="ChampionUser", xp=5000),
        LeaderboardEntry(position=2, nickname="RunnerUp", xp=4500),
        LeaderboardEntry(position=3, nickname="ThirdPlace", xp=4000),
    ]
