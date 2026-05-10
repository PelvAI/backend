from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.session import Base
import uuid
from datetime import datetime

class Season(Base):
    __tablename__ = "seasons"
    season_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String)
    start_date = Column(DateTime)
    end_date = Column(DateTime)

class Currency(Base):
    __tablename__ = "currencies"
    currency_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String, unique=True) # XP, COINS

    wallets = relationship("Wallet", back_populates="currency")
    shop_items = relationship("ShopItem", back_populates="currency")

class Wallet(Base):
    __tablename__ = "user_wallet"
    wallet_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    currency_id = Column(UUID(as_uuid=True), ForeignKey("currencies.currency_id"))
    balance = Column(Integer, default=0)

    user = relationship("User", back_populates="wallet")
    currency = relationship("Currency", back_populates="wallets")
    transactions = relationship("Transaction", back_populates="wallet")

class Transaction(Base):
    __tablename__ = "transactions"
    transaction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("user_wallet.wallet_id"))
    amount = Column(Integer)
    source = Column(String) # "session_reward", "shop_purchase"

    wallet = relationship("Wallet", back_populates="transactions")

class ShopItem(Base):
    __tablename__ = "shop_catalog"
    item_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name_key = Column(String)
    cost_currency_id = Column(UUID(as_uuid=True), ForeignKey("currencies.currency_id"))
    cost_amount = Column(Integer)

    currency = relationship("Currency", back_populates="shop_items")
    inventory_items = relationship("UserInventory", back_populates="item")

class UserInventory(Base):
    __tablename__ = "user_inventory"
    inventory_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    item_id = Column(UUID(as_uuid=True), ForeignKey("shop_catalog.item_id"))
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="inventory")
    item = relationship("ShopItem", back_populates="inventory_items")

class UserStreak(Base):
    __tablename__ = "user_streaks"
    streak_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), unique=True)
    current_streak = Column(Integer, default=0)
    max_streak = Column(Integer, default=0)
    last_activity_date = Column(DateTime)
    
    user = relationship("User", back_populates="streak")
