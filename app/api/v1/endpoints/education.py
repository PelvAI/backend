from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.education import EducationModule
from app.schemas.education import EducationModuleResponse
from typing import List
from app.api import deps
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=List[EducationModuleResponse])
async def list_education_modules(
    category: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    List education modules, optionally filtered by category.
    """
    query = select(EducationModule).where(EducationModule.is_active == True)
    
    if category:
        query = query.where(EducationModule.category == category)
        
    result = await db.execute(query)
    return result.scalars().all()
