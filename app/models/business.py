from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base
import uuid
from datetime import datetime
import enum

class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    EXPIRED = "expired"
    PAST_DUE = "past_due"

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    plan_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stripe_product_id = Column(String)
    name = Column(String)

    subscriptions = relationship("UserSubscription", back_populates="plan")

class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    subscription_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    plan_id = Column(UUID(as_uuid=True), ForeignKey("subscription_plans.plan_id"))
    status = Column(Enum(SubscriptionStatus))
    ad_free_enabled = Column(Boolean, default=False)

    user = relationship("app.models.user.User", backref="subscription")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")

class AdCampaign(Base):
    __tablename__ = "ad_campaigns"
    campaign_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sponsor_name = Column(String)
    asset_url = Column(String)
    target_tags = Column(JSONB)

class AdPlacement(Base):
    __tablename__ = "ad_placements"
    placement_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    location_code = Column(String)
