from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.models.map import LearningPath, PathNode, UserPathProgress, NodeContent, NodeRequirement
from app.models.user import User
from app.schemas.map import LearningPathResponse, PathNodeResponse, UserPathProgressResponse
from app.api import deps
from uuid import UUID
from typing import List

router = APIRouter()

@router.get("/paths", response_model=List[LearningPathResponse])
async def list_paths(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    List available learning paths (worlds).
    """
    result = await db.execute(select(LearningPath))
    return result.scalars().all()

@router.get("/paths/{path_id}/nodes", response_model=List[PathNodeResponse])
async def get_path_nodes(
    path_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get nodes for a specific path (for drawing the map).
    """
    result = await db.execute(
        select(PathNode)
        .options(selectinload(PathNode.content))
        .where(PathNode.path_id == path_id)
    )
    return result.scalars().all()

@router.get("/nodes/{node_id}/details", response_model=PathNodeResponse)
async def get_node_details(
    node_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get node details (if unlocked).
    """
    # Logic to check if unlocked (check requirements) omitted for brevity
    result = await db.execute(
        select(PathNode)
        .options(selectinload(PathNode.content))
        .where(PathNode.node_id == node_id)
    )
    node = result.scalars().first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node

@router.post("/nodes/{node_id}/start")
async def start_node(
    node_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Attempt to start a node (verify requirements).
    """
    # Check requirements logic here
    return {"message": "Node started", "node_id": node_id}

@router.post("/nodes/{node_id}/complete", response_model=UserPathProgressResponse)
async def complete_node(
    node_id: UUID,
    stars: int = 3,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Mark node as completed.
    """
    progress = UserPathProgress(
        user_id=current_user.user_id,
        node_id=node_id,
        stars_earned=stars
    )
    db.add(progress)
    await db.commit()
    await db.refresh(progress)
    return progress
