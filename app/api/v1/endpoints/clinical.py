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
    ScoringRule, ClinicalAlert, FormStatus, Target
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
        await db.refresh(current_user.profile, ["targets"])

    # 2. Build query
    query = select(ClinicalForm).options(
        selectinload(ClinicalForm.targets),
        selectinload(ClinicalForm.scoring_rules),
        selectinload(ClinicalForm.sections)
        .selectinload(FormSection.questions)
        .selectinload(FormQuestion.options)
    ).where(
        ClinicalForm.is_active == True,
        # Sólo lo publicado llega a la usuaria. Antes se filtraba únicamente por
        # is_active, de modo que un borrador a medio escribir quedaba visible
        # apenas se creaba y el acto de publicar no existía (F2).
        ClinicalForm.status == FormStatus.ACTIVE,
    )

    # 3. Apply Filtering
    from sqlalchemy import or_

    # Always allow forms with "todas" target (case-insensitive) OR forms with NO targets assigned
    filter_conditions = [
        ClinicalForm.targets.any(Target.code.ilike("todas")),
        ~ClinicalForm.targets.any() # Include forms with no targets
    ]
    
    if target:
        # Manual override via query param
        filter_conditions.append(ClinicalForm.targets.any(Target.code == target.upper()))
    elif current_user.profile and current_user.profile.targets:
        # Automatic filtering by user's clinical tags
        user_target_ids = [t.target_id for t in current_user.profile.targets]
        filter_conditions.append(ClinicalForm.targets.any(Target.target_id.in_(user_target_ids)))
        
    query = query.where(or_(*filter_conditions))
        
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
        # Mismo criterio que el listado: un borrador no debe poder abrirse
        # adivinando su código.
        .where(ClinicalForm.status == FormStatus.ACTIVE)
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

    # 1. Los segmentos clínicos de la usuaria entran al motor: sin ellos, toda
    #    regla y toda opción con condición de segmento se descarta (F15, F16).
    user_target_ids = []
    if current_user.profile:
        await TagAutomationService.sync_profile_tags(db, current_user.profile.profile_id)
        await db.refresh(current_user.profile, ["targets"])
        user_target_ids = [str(t.target_id) for t in current_user.profile.targets]

    questions = [q for section in form.sections for q in section.questions]
    raw_answers = {ans.question_id: ans.value for ans in submission.answers}

    # 2. Camino único, el mismo que ejecuta el simulador del panel.
    engine = ScoringEngine()
    resultado = engine.score_submission(
        questions, form.scoring_rules, raw_answers, user_target_ids=user_target_ids
    )

    # 3. Persistir el puntaje de cada respuesta
    puntajes = {a.question_id: a.score for a in resultado.answer_scores}
    for ans in submission.answers:
        if ans.question_id in puntajes:
            ans.score = int(puntajes[ans.question_id])

    # 4. Guardar el resultado. calculated_values conserva su forma anterior a
    #    propósito: es el contexto que RecommendationService usa para asignar
    #    planes de entrenamiento.
    submission.calculated_values = resultado.values
    submission.total_score = resultado.total_score
    submission.score_interpretation = resultado.interpretation
    submission.completed_at = datetime.utcnow()

    # 5. Create Clinical Alerts (Persist)
    for res in resultado.alerts:
        alert = ClinicalAlert(
            user_id=current_user.user_id,
            submission_id=submission.submission_id,
            rule_id=UUID(res.rule_id) if res.rule_id else None,
            alert_type=res.alert_type,
            triggered_value=res.triggered_value,
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
