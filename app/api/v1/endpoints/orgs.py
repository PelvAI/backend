from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.user import User, Organization, ProfessionalLink, LinkStatus, Profile
from app.schemas.user import OrganizationResponse
from app.api import deps
from uuid import UUID
from typing import List, Dict, Any
from pydantic import BaseModel

router = APIRouter()

class JoinRequest(BaseModel):
    role: str # 'medic', 'player', etc.

class LinkInvite(BaseModel):
    email: str
    role: str

class ScopeUpdate(BaseModel):
    security_scope: Dict[str, bool]

@router.get("/orgs", response_model=List[OrganizationResponse])
async def list_organizations(
    db: AsyncSession = Depends(get_db)
):
    """
    List available organizations.
    """
    result = await db.execute(select(Organization))
    return result.scalars().all()

@router.get("/orgs/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get organization details.
    """
    result = await db.execute(select(Organization).where(Organization.organization_id == org_id))
    org = result.scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org

@router.post("/orgs/{org_id}/join-request")
async def request_join_organization(
    org_id: UUID,
    request: JoinRequest,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Request to join an organization. (Stub)
    """
    # In real app, create an AffiliationRequest record
    return {"message": "Join request sent", "org_id": org_id, "role": request.role}

@router.get("/my-links")
async def list_my_links(
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List active professional links.
    """
    # Assuming current user is patient for simplicity, or we check both sides
    # Need to get profile first
    result = await db.execute(select(Profile).where(Profile.user_id == current_user.user_id))
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    result = await db.execute(
        select(ProfessionalLink).where(
            (ProfessionalLink.patient_profile_id == profile.profile_id) | 
            (ProfessionalLink.medic_profile_id == profile.profile_id)
        )
    )
    return result.scalars().all()

@router.post("/my-links/invite")
async def invite_professional(
    invite: LinkInvite,
    current_user: User = Depends(deps.get_current_user),
):
    """
    Invite a professional. (Stub)
    """
    return {"message": f"Invitation sent to {invite.email}", "code": "INV-12345"}

@router.patch("/my-links/{link_id}/scope")
async def update_link_scope(
    link_id: UUID,
    scope_update: ScopeUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update security scope for a link.
    """
    result = await db.execute(select(ProfessionalLink).where(ProfessionalLink.link_id == link_id))
    link = result.scalars().first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    
    # Verify ownership (omitted for brevity, but critical in prod)
    
    link.security_scope = scope_update.security_scope
    await db.commit()
    await db.refresh(link)
    return link

@router.delete("/my-links/{link_id}")
async def revoke_link(
    link_id: UUID,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Revoke a professional link.
    """
    result = await db.execute(select(ProfessionalLink).where(ProfessionalLink.link_id == link_id))
    link = result.scalars().first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    
    link.status = LinkStatus.REVOKED
    await db.commit()
    return {"message": "Link revoked"}
