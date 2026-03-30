from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.models.clinical import (
    ClinicalForm, UserSubmission, SubmissionAnswer, FormSection, FormQuestion,
    TargetType, FormStatus, ScoringRule, ClinicalAlert, AlertType, ScoreMode, Target
)
from app.models.user import User
from app.schemas.clinical import FormResponse, SubmissionCreate, SubmissionResponse, SubmissionUpdate, ClinicalSnapshotResponse
from app.services.scoring import ScoringEngine
from app.services.recommendations import RecommendationService, GamificationService
from app.api import deps

from app.services.automation import TagAutomationService

router = APIRouter()

@router.get("/forms", response_model=List[FormResponse])
async def list_forms(
    target: Optional[str] = None, # Changed from TargetType to str for flexibility
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    List available clinical forms.
    Filters by Target Audience (e.g. PREGNANT) and Status=ACTIVE.
    If no target is provided, automatically uses the user's synced clinical tags.
    """
    # 1. Ensure user tags are synced (Temporal Logic)
    if current_user.profile:
        await TagAutomationService.sync_profile_tags(db, current_user.profile.profile_id)
        # Refresh user to get updated targets if needed, 
        # though sync_profile_tags might be enough.
        # For filtering, we'll use the Profile.targets collection.
        await db.refresh(current_user.profile, ["targets"])

    # 2. Build query
    query = select(ClinicalForm).options(
        selectinload(ClinicalForm.targets),
        selectinload(ClinicalForm.scoring_rules),
        selectinload(ClinicalForm.sections)
        .selectinload(FormSection.questions)
        .selectinload(FormQuestion.options)
    ).where(
        ClinicalForm.is_active == True
    )
    
    # 3. Apply Filtering
    if target:
        # Manual override via query param
        query = query.where(ClinicalForm.targets.any(Target.code == target.upper()))
    elif current_user.profile and current_user.profile.targets:
        # Automatic filtering by user's clinical tags
        user_target_ids = [t.target_id for t in current_user.profile.targets]
        query = query.join(ClinicalForm.targets).where(Target.target_id.in_(user_target_ids))
    else:
        # Fallback: only show "todas" forms (General Audience)
        query = query.where(ClinicalForm.targets.any(Target.code == "todas"))
        
    result = await db.execute(query)
    # Remove duplicates from join if any
    forms = result.scalars().unique().all()
    return forms

@router.get("/forms/{code}/schema", response_model=FormResponse)
async def get_form_schema(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get full form schema by code.
    """
    result = await db.execute(
        select(ClinicalForm)
        .options(
            selectinload(ClinicalForm.targets),
            selectinload(ClinicalForm.scoring_rules),
            selectinload(ClinicalForm.sections)
            .selectinload(FormSection.questions)
            .selectinload(FormQuestion.options)
        )
        .where(ClinicalForm.code == code)
        .where(ClinicalForm.is_active == True)
    )
    form = result.scalars().first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    form.sections.sort(key=lambda x: x.order_index)
    return form

@router.post("/submissions/start", response_model=SubmissionResponse)
async def start_submission(
    submission_in: SubmissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Start a new empty submission.
    """
    submission = UserSubmission(
        user_id=current_user.user_id,
        form_id=submission_in.form_id
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    return submission

@router.put("/submissions/{sub_id}/answers", response_model=SubmissionResponse)
async def save_answers(
    sub_id: UUID,
    update_in: SubmissionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Save partial answers (Draft mode).
    """
    result = await db.execute(select(UserSubmission).where(UserSubmission.submission_id == sub_id))
    submission = result.scalars().first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Clear old answers for simplicity in this stub, or update/upsert
    # For MVP, we'll just add new ones (ignoring duplicates logic for now)
    for answer_in in update_in.answers:
        answer = SubmissionAnswer(
            submission_id=submission.submission_id,
            question_id=answer_in.question_id,
            value=answer_in.value
        )
        db.add(answer)
    
    await db.commit()
    await db.refresh(submission)
    return submission

@router.post("/submissions/{sub_id}/finalize", response_model=SubmissionResponse)
async def finalize_submission(
    sub_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Finalize submission and trigger scoring.
    """
    # Load Submission with Answers
    result = await db.execute(
        select(UserSubmission)
        .where(UserSubmission.submission_id == sub_id)
        .options(selectinload(UserSubmission.answers))
    )
    submission = result.scalars().first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
        
    # Load Form with Rules and Questions (to map answers)
    form_res = await db.execute(
        select(ClinicalForm)
        .where(ClinicalForm.form_id == submission.form_id)
        .options(
            selectinload(ClinicalForm.scoring_rules),
            selectinload(ClinicalForm.sections)
            .selectinload(FormSection.questions)
            .selectinload(FormQuestion.options)
        )
    )
    form = form_res.scalars().first()
    if not form:
        raise HTTPException(status_code=404, detail="Form definition not found")

    # 1. Resolve Scores for Answers and Build Context
    questions_map = {}
    for section in form.sections:
        for q in section.questions:
            questions_map[q.question_id] = q
            
    resolved_context = {}
    
    for ans in submission.answers:
        q = questions_map.get(ans.question_id)
        if not q:
            continue
            
        # Calc score for this answer
        resolved_score = 0
        raw_val = ans.value
        
        if q.score_mode == ScoreMode.OPTION_SCORE and q.options:
            for opt in q.options:
                # Compare as strings to be safe
                if str(opt.value) == str(raw_val):
                    resolved_score = opt.score
                    break
        elif q.score_mode == ScoreMode.VALUE_AS_SCORE:
            try:
                resolved_score = float(raw_val)
            except:
                resolved_score = 0
        
        # Update Answer Row
        ans.score = int(resolved_score) # assuming integer col? It is Integer.
        
        # Update Context for Engine (if it has data_key)
        if q.data_key:
            resolved_context[q.data_key] = resolved_score

    # 2. Run Scoring Engine
    engine = ScoringEngine()
    scores, alert_results = engine.process_rules(form.scoring_rules, resolved_context)
    
    # 3. Save Calculated Values
    submission.total_score = scores.get('total_score') or scores.get('iciq_total') or 0 # Heuristic or define strict rule
    # For ICIQ-SF specifically, we used 'iciq_total'. 
    # General solution: store ALL scores in calculated_values
    submission.calculated_values = scores
    
    # Update total_score strictly if there is a 'total' key, or first value?
    # Let's try to find a key ending in '_total' or just use first.
    if scores:
        # Check rule mapping variable_name to see which is 'main'.
        # For now, just Dump JSON. Mobile can parse.
        # But UserSubmission has 'total_score' Float column.
        # Let's pick 'iciq_total' if exists.
        if 'iciq_total' in scores:
            submission.total_score = scores['iciq_total']
        elif 'total_score' in scores:
             submission.total_score = scores['total_score']
    
    submission.completed_at = datetime.utcnow()
    
    # 4. Create Clinical Alerts (Persist)
    for res in alert_results:
        # Check if alert already exists? (Maybe retrying finalization)
        # For MVP, just add.
        alert = ClinicalAlert(
            user_id=current_user.user_id,
            submission_id=submission.submission_id,
            rule_id=UUID(res.rule_id), # AlertResult stores str, convert to UUID
            alert_type=res.alert_type, # Enum value matching
            triggered_value=0, # We didn't capture WHAT value triggered it easily in AlertResult yet. 
            # (TODO: Add triggered_value to AlertResult in scoring logic later)
            is_shown_to_user=True # Default
        )
        db.add(alert)
    
    # 5. Run Recommendations & Gamification
    await RecommendationService.evaluate_submission(db, submission)
    await GamificationService.update_streak(db, current_user.user_id)
    
    await db.commit()
    await db.refresh(submission)
    
    return submission

@router.get("/submissions/history", response_model=List[SubmissionResponse])
async def get_submission_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get submission history.
    """
    result = await db.execute(
        select(UserSubmission)
        .where(UserSubmission.user_id == current_user.user_id)
        .order_by(UserSubmission.created_at.desc())
    )
    return result.scalars().all()

from app.models.clinical import ClinicalSnapshot
from app.schemas.clinical import ClinicalSnapshotResponse

@router.get("/snapshots/latest", response_model=ClinicalSnapshotResponse)
async def get_latest_snapshot(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get latest clinical snapshot.
    """
    result = await db.execute(
        select(ClinicalSnapshot)
        .where(ClinicalSnapshot.user_id == current_user.user_id)
        .order_by(ClinicalSnapshot.last_updated.desc())
    )
    snapshot = result.scalars().first()
    if not snapshot:
        # Return empty/default snapshot
        return ClinicalSnapshotResponse(
            snapshot_id=UUID("00000000-0000-0000-0000-000000000000"),
            last_updated=datetime.utcnow(),
            data={}
        )
    return snapshot

@router.get("/snapshots/history", response_model=List[ClinicalSnapshotResponse])
async def get_snapshot_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get clinical snapshot history.
    """
    result = await db.execute(
        select(ClinicalSnapshot)
        .where(ClinicalSnapshot.user_id == current_user.user_id)
        .order_by(ClinicalSnapshot.last_updated.asc())
    )
    return result.scalars().all()
