from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import Optional, List, Any, Dict

class SubscriptionPlanResponse(BaseModel):
    plan_id: UUID
    stripe_product_id: str
    name: str
    model_config = ConfigDict(from_attributes=True)

class CheckoutSessionCreate(BaseModel):
    plan_id: UUID

class CheckoutSessionResponse(BaseModel):
    checkout_url: str

class AdPlacementResponse(BaseModel):
    placement_id: UUID
    location_code: str
    campaign_id: UUID
    asset_url: str
    sponsor_name: str
    model_config = ConfigDict(from_attributes=True)
