from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.models.training import UserAssignment, SessionTemplate, AssignmentStatus, SessionPerformance, Exercise
from app.models.user import User
from app.schemas.training import AssignmentResponse, SessionCompletion, SessionProgress, ExerciseResponse
from typing import List
from uuid import UUID
from app.api import deps
from datetime import date

router = APIRouter()

@router.get("/daily-plan", response_model=AssignmentResponse)
async def get_daily_plan(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get the training assignment for today (Smart Endpoint).
    """
    today = date.today()
    
    # Check for existing assignment today
    result = await db.execute(
        select(UserAssignment)
        .options(selectinload(UserAssignment.template))
        .where(UserAssignment.user_id == current_user.user_id)
        .where(UserAssignment.date == today)
    )
    assignment = result.scalars().first()
    
    if not assignment:
        # For MVP/Testing: Find ANY pending assignment or create a dummy one?
        # Let's try to find any pending assignment
        result = await db.execute(
            select(UserAssignment)
            .options(selectinload(UserAssignment.template))
            .where(UserAssignment.user_id == current_user.user_id)
            .where(UserAssignment.status == AssignmentStatus.PENDING)
            .order_by(UserAssignment.date)
        )
        assignment = result.scalars().first()
        
    if not assignment:
        raise HTTPException(status_code=404, detail="No training assigned for today")
        
    return assignment

@router.get("/exercises/library", response_model=List[ExerciseResponse])
async def list_exercises(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    List all exercises (Library).
    """
    result = await db.execute(select(Exercise))
    return result.scalars().all()

@router.get("/exercises/{exercise_id}", response_model=ExerciseResponse)
async def get_exercise(
    exercise_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get exercise details.
    """
    result = await db.execute(select(Exercise).where(Exercise.exercise_id == exercise_id))
    exercise = result.scalars().first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise

@router.post("/session/{assign_id}/progress")
async def update_session_progress(
    assign_id: UUID,
    progress: SessionProgress,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Mark specific exercise as completed (Stub).
    """
    # In real app, update a JSONB field or separate table for intra-session progress
    return {"message": "Progress recorded", "exercise_id": progress.exercise_id}

@router.post("/session/{assign_id}/feedback", response_model=AssignmentResponse)
async def submit_session_feedback(
    assign_id: UUID,
    completion_in: SessionCompletion,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Complete session and submit feedback.
    """
    result = await db.execute(
        select(UserAssignment)
        .where(UserAssignment.assignment_id == assign_id)
        .where(UserAssignment.user_id == current_user.user_id)
    )
    assignment = result.scalars().first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    if assignment.status == AssignmentStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Session already completed")
        
    # Update status
    assignment.status = AssignmentStatus.COMPLETED
    
    # Record Performance
    perf = SessionPerformance(
        assignment_id=assignment.assignment_id,
        duration_actual=completion_in.duration_actual,
        perceived_exertion=completion_in.perceived_exertion,
        pain_reported=completion_in.pain_reported
    )
    db.add(perf)
    
    await db.commit()
    await db.refresh(assignment)
    
    # Re-fetch with template for response
    result = await db.execute(
        select(UserAssignment)
        .options(selectinload(UserAssignment.template))
        .where(UserAssignment.assignment_id == assignment.assignment_id)
    )
    assignment = result.scalars().first()
    
    return assignment
