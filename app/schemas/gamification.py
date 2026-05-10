from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List

class WalletResponse(BaseModel):
    balance: int
    currency_code: str
    model_config = ConfigDict(from_attributes=True)

class TransactionResponse(BaseModel):
    transaction_id: UUID
    amount: int
    source: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ShopItemResponse(BaseModel):
    item_id: UUID
    name_key: str
    cost_amount: int
    cost_currency_id: UUID
    model_config = ConfigDict(from_attributes=True)

class UserInventoryResponse(BaseModel):
    inventory_id: UUID
    item_id: UUID
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

class SeasonResponse(BaseModel):
    season_id: UUID
    name: str
    end_date: datetime
    model_config = ConfigDict(from_attributes=True)

class LeaderboardEntry(BaseModel):
    position: int
    nickname: str
    xp: int

class UserStats(BaseModel):
    xp: int
    streak: int
    league: str
    league_position: int
    wellness_index: int
    level: int
    program_week: int
