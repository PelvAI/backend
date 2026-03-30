from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.models.business import SubscriptionPlan, AdPlacement, AdCampaign
from app.models.user import User
from app.schemas.subscriptions import SubscriptionPlanResponse, CheckoutSessionCreate, CheckoutSessionResponse, AdPlacementResponse
from app.api import deps
from uuid import UUID
from typing import List

router = APIRouter()

@router.get("/subscriptions/plans", response_model=List[SubscriptionPlanResponse])
async def list_plans(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    List available subscription plans.
    """
    result = await db.execute(select(SubscriptionPlan))
    return result.scalars().all()

@router.post("/subscriptions/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    checkout_in: CheckoutSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Create Stripe checkout session. (Stub)
    """
    # In real app: Call Stripe API to create session
    return {"checkout_url": "https://checkout.stripe.com/pay/stub_session_id"}

@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request
):
    """
    Handle Stripe webhooks. (Stub)
    """
    # In real app: Verify signature, parse event, update UserSubscription
    return {"status": "received"}

@router.get("/ads/placements/{location}", response_model=AdPlacementResponse)
async def get_ad_placement(
    location: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get ad placement for a specific location.
    """
    # Join with Campaign to get asset details
    result = await db.execute(
        select(AdPlacement)
        .options(selectinload(AdPlacement.campaign))
        .where(AdPlacement.location_code == location)
    )
    placement = result.scalars().first()
    
    if not placement:
        raise HTTPException(status_code=404, detail="No ad found for this location")
        
    # Construct response manually since model structure might differ slightly from flat response
    return AdPlacementResponse(
        placement_id=placement.placement_id,
        location_code=placement.location_code,
        campaign_id=placement.campaign_id,
        asset_url=placement.campaign.asset_url,
        sponsor_name=placement.campaign.sponsor_name
    )
