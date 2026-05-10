"""
Admin endpoints for Clinical Forms management.
Provides full CRUD operations for forms, sections, questions, options, and scoring rules.
Optimized for performance with pagination and server-side filtering.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.db.session import get_db
from app.api.deps import get_current_admin
from app.models.user import User
from app.models.clinical import (
    ClinicalForm, FormSection, FormQuestion, AnswerOption, 
    ScoringRule, FormStatus, TargetType, FrecuenciaType, DisparadorType,
    QuestionType, ValueType, ScoreMode, UIHint, AlertType
)
from app.schemas.clinical import TargetCreate, TargetUpdate, TargetResponse
from pydantic import BaseModel, Field
from datetime import datetime

router = APIRouter()


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

# --- Answer Options ---
class OptionCreate(BaseModel):
    value: str
    label_key: Optional[str] = None
    score: int = 0
    context_rules: Optional[List[dict]] = None
    order_index: int = 0

class OptionUpdate(BaseModel):
    value: Optional[str] = None
    label_key: Optional[str] = None
    score: Optional[int] = None
    context_rules: Optional[List[dict]] = None
    order_index: Optional[int] = None

class OptionResponse(BaseModel):
    option_id: UUID
    value: str
    label_key: Optional[str]
    score: int
    context_rules: Optional[List[dict]]
    order_index: int
    
    class Config:
        from_attributes = True


# --- Questions ---
class QuestionCreate(BaseModel):
    id_pregunta: Optional[str] = None  # e.g., URIN01_DISPARADORA
    variable_name: Optional[str] = None  # Human readable name
    data_key: Optional[str] = None  # For formulas: iciq_frecuencia
    text_key: Optional[str] = None
    type: QuestionType
    value_type: ValueType = ValueType.STRING
    score_mode: ScoreMode = ScoreMode.NONE
    show_if: Optional[str] = None
    help_text: Optional[str] = None
    placeholder: Optional[str] = None
    ui_hint: Optional[UIHint] = None
    is_required: bool = False
    order_index: int = 0
    options: Optional[List[OptionCreate]] = None

class QuestionUpdate(BaseModel):
    id_pregunta: Optional[str] = None
    variable_name: Optional[str] = None
    data_key: Optional[str] = None
    text_key: Optional[str] = None
    type: Optional[QuestionType] = None
    value_type: Optional[ValueType] = None
    score_mode: Optional[ScoreMode] = None
    show_if: Optional[str] = None
    help_text: Optional[str] = None
    placeholder: Optional[str] = None
    ui_hint: Optional[UIHint] = None
    is_required: Optional[bool] = None
    order_index: Optional[int] = None

class QuestionResponse(BaseModel):
    question_id: UUID
    id_pregunta: Optional[str]
    variable_name: Optional[str]
    data_key: Optional[str]
    text_key: Optional[str]
    type: QuestionType
    value_type: Optional[ValueType]
    score_mode: Optional[ScoreMode]
    show_if: Optional[str]
    help_text: Optional[str]
    placeholder: Optional[str]
    ui_hint: Optional[UIHint]
    is_required: Optional[bool]
    order_index: Optional[int]
    options: List[OptionResponse] = []
    
    class Config:
        from_attributes = True


# --- Sections ---
class SectionCreate(BaseModel):
    title_key: Optional[str] = None
    bloque: Optional[str] = None  # e.g., "URIN", "PROL"
    order_index: int = 0

class SectionUpdate(BaseModel):
    title_key: Optional[str] = None
    bloque: Optional[str] = None
    order_index: Optional[int] = None

class SectionResponse(BaseModel):
    section_id: UUID
    title_key: Optional[str]
    bloque: Optional[str]
    order_index: Optional[int]
    questions: List[QuestionResponse] = []
    
    class Config:
        from_attributes = True


# --- Scoring Rules ---
class ScoringRuleCreate(BaseModel):
    variable_name: str  # e.g., "iciq_total"
    formula: Optional[str] = None  # e.g., "iciq_frecuencia + iciq_cantidad"
    interpretation_ranges: Optional[dict] = None
    alert_condition: Optional[str] = None  # e.g., "value >= 10"
    alert_type: Optional[AlertType] = None
    target_id: Optional[UUID] = None
    order_index: int = 0

class ScoringRuleUpdate(BaseModel):
    variable_name: Optional[str] = None
    formula: Optional[str] = None
    interpretation_ranges: Optional[dict] = None
    alert_condition: Optional[str] = None
    alert_type: Optional[AlertType] = None
    target_id: Optional[UUID] = None
    order_index: Optional[int] = None

class ScoringRuleResponse(BaseModel):
    rule_id: UUID
    variable_name: str
    formula: Optional[str]
    interpretation_ranges: Optional[dict]
    alert_condition: Optional[str]
    alert_type: Optional[AlertType]
    target_id: Optional[UUID]
    order_index: Optional[int]
    
    class Config:
        from_attributes = True


# --- Forms ---
# --- Forms ---
class FormCreate(BaseModel):
    code: str
    title_key: Optional[str] = None
    description_key: Optional[str] = None
    target_ids: List[UUID] = []
    frecuencia: FrecuenciaType = FrecuenciaType.UNICA_VEZ
    disparador: DisparadorType = DisparadorType.AL_REGISTRO

class FormUpdate(BaseModel):
    code: Optional[str] = None
    title_key: Optional[str] = None
    description_key: Optional[str] = None
    status: Optional[FormStatus] = None
    target_ids: Optional[List[UUID]] = None
    frecuencia: Optional[FrecuenciaType] = None
    disparador: Optional[DisparadorType] = None

class FormListResponse(BaseModel):
    form_id: UUID
    code: str
    title_key: Optional[str]
    version: int
    status: Optional[FormStatus]
    targets: List[TargetResponse] = []
    frecuencia: Optional[FrecuenciaType]
    is_active: bool
    question_count: int = 0
    created_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class FormDetailResponse(BaseModel):
    form_id: UUID
    code: str
    title_key: Optional[str]
    description_key: Optional[str]
    version: int
    status: Optional[FormStatus]
    is_active: bool
    targets: List[TargetResponse] = []
    frecuencia: Optional[FrecuenciaType]
    disparador: Optional[DisparadorType]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    sections: List[SectionResponse] = []
    scoring_rules: List[ScoringRuleResponse] = []
    
    class Config:
        from_attributes = True

class FormPagination(BaseModel):
    total: int
    page: int
    size: int
    items: List[FormListResponse]


# --- Target Schemas ---
# Defined in app.schemas.clinical but imported/used here for endpoints
from app.schemas.clinical import TargetCreate, TargetUpdate, TargetResponse

# =============================================================================
# TARGET ENDPOINTS (NEW)
# =============================================================================

@router.post("/targets", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
async def create_target(
    target_in: TargetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    from app.models.clinical import Target
    target = Target(**target_in.model_dump())
    db.add(target)
    try:
        await db.commit()
        await db.refresh(target)
        return target
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/targets", response_model=List[TargetResponse])
async def list_targets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    from app.models.clinical import Target
    result = await db.execute(select(Target).where(Target.is_active == True))
    return result.scalars().all()


# =============================================================================
# FORM ENDPOINTS
# =============================================================================

@router.get("/forms", response_model=FormPagination)
async def list_forms(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[FormStatus] = None,
    target_code: Optional[str] = None,   # Filter by target code e.g. 'embarazadas'
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    List clinical forms with pagination and backend filtering.
    Optimized to return only necessary fields for list view.
    """
    from app.models.clinical import Target

    # Base query for counting
    count_query = select(func.count(ClinicalForm.form_id)).where(ClinicalForm.is_active == True)

    # Base query for fetching (No eager load options to avoid async issues)
    query = select(ClinicalForm).where(ClinicalForm.is_active == True)
    
    # Apply filters
    if status:
        count_query = count_query.where(ClinicalForm.status == status)
        query = query.where(ClinicalForm.status == status)
    
    if target_code:
        # Filter where form has the specific target
        count_query = count_query.where(ClinicalForm.targets.any(Target.code == target_code))
        query = query.where(ClinicalForm.targets.any(Target.code == target_code))
        
    if search:
        count_query = count_query.where(ClinicalForm.code.ilike(f"%{search}%"))
        query = query.where(ClinicalForm.code.ilike(f"%{search}%"))
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Get items
    query = query.order_by(ClinicalForm.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    forms = result.scalars().all()
    
    items = []
    for form in forms:
        # Manual question count per item
        q_count = await db.scalar(
            select(func.count(FormQuestion.question_id))
            .join(FormSection)
            .where(FormSection.form_id == form.form_id)
        )
        
        # Manual targets fetch
        targets_result = await db.execute(
            select(Target)
            .join(ClinicalForm.targets) # Join through relationship
            .where(ClinicalForm.form_id == form.form_id)
        )
        # Or simpler if relationship logic is complex:
        # targets_result = await db.execute(select(Target).where(Target.forms.any(ClinicalForm.form_id == form.form_id)))
        # But using relationship join works if relationship is correct.
        # Let's use direct relationship join logic from model:
        # form.targets is relationship.
        # We can query Target where Target.forms contains 'form'.
        targets = targets_result.scalars().all()
        
        items.append(FormListResponse(
            form_id=form.form_id,
            code=form.code,
            title_key=form.title_key,
            version=form.version,
            status=form.status,
            targets=targets,
            frecuencia=form.frecuencia,
            is_active=form.is_active,
            question_count=q_count or 0,
            created_at=form.created_at
        ))
    
    return FormPagination(total=total, page=(skip // limit) + 1, size=limit, items=items)


@router.post("/forms", response_model=FormDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_form(
    form_data: FormCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Create a new clinical form."""
    existing = await db.execute(
        select(ClinicalForm)
        .where(ClinicalForm.code == form_data.code)
        .options(selectinload(ClinicalForm.targets))
    )
    existing_form = existing.scalar()
    
    if existing_form:
        if not existing_form.is_active:
            # Reactivate soft-deleted form
            existing_form.is_active = True
            existing_form.status = FormStatus.DRAFT
            existing_form.title_key = form_data.title_key
            existing_form.description_key = form_data.description_key
            
            # Handle Targets
            if form_data.target_ids:
                from app.models.clinical import Target
                targets_res = await db.execute(select(Target).where(Target.target_id.in_(form_data.target_ids)))
                existing_form.targets = targets_res.scalars().all()
            
            existing_form.frecuencia = form_data.frecuencia
            existing_form.disparador = form_data.disparador
            
            await db.commit()
            await db.refresh(existing_form)
            
            return await get_form(existing_form.form_id, db=db, current_user=current_user)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Form with code '{form_data.code}' already exists"
            )
    
    form = ClinicalForm(
        code=form_data.code,
        title_key=form_data.title_key,
        description_key=form_data.description_key,
        frecuencia=form_data.frecuencia,
        disparador=form_data.disparador,
        status=FormStatus.DRAFT,
        version=1,
        is_active=True
    )
    
    db.add(form)
    
    # Link Targets
    if form_data.target_ids:
        from app.models.clinical import Target
        targets_result = await db.execute(select(Target).where(Target.target_id.in_(form_data.target_ids)))
        targets = targets_result.scalars().all()
        form.targets = targets

    await db.commit()
    await db.refresh(form)
    
    return await get_form(form.form_id, db=db, current_user=current_user)


@router.get("/forms/{form_id}", response_model=FormDetailResponse)
async def get_form(
    form_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get a form with all its relationships loaded efficiently.
    Uses 'selectinload' to prevent N+1 query problems.
    """
    result = await db.execute(
        select(ClinicalForm)
        .where(ClinicalForm.form_id == form_id)
        .options(
            selectinload(ClinicalForm.sections)
            .selectinload(FormSection.questions)
            .selectinload(FormQuestion.options),
            selectinload(ClinicalForm.scoring_rules),
            selectinload(ClinicalForm.targets)
        )
    )
    form = result.scalar()
    
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    return form


@router.put("/forms/{form_id}", response_model=FormDetailResponse)
async def update_form(
    form_id: UUID,
    form_data: FormUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update a form's metadata."""
    result = await db.execute(
        select(ClinicalForm)
        .where(ClinicalForm.form_id == form_id)
        .options(joinedload(ClinicalForm.targets))
    )
    form = result.unique().scalar_one_or_none()
    
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    update_data = form_data.model_dump(exclude_unset=True)
    
    # Handle Targets
    if 'target_ids' in update_data:
        target_ids = update_data.pop('target_ids')
        if target_ids is not None:
            from app.models.clinical import Target
            targets_res = await db.execute(select(Target).where(Target.target_id.in_(target_ids)))
            form.targets = targets_res.scalars().all()

    for field, value in update_data.items():
        if hasattr(form, field):
            setattr(form, field, value)
    
    await db.commit()
    await db.refresh(form)
    
    return await get_form(form.form_id, db=db, current_user=current_user)


@router.delete("/forms/{form_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_form(
    form_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Soft delete a form (sets is_active to False)."""
    result = await db.execute(
        select(ClinicalForm).where(ClinicalForm.form_id == form_id)
    )
    form = result.scalar()
    
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    form.is_active = False
    form.status = FormStatus.ARCHIVED
    await db.commit()


# =============================================================================
# SECTION ENDPOINTS
# =============================================================================

@router.post("/forms/{form_id}/sections", response_model=SectionResponse, status_code=status.HTTP_201_CREATED)
async def create_section(
    form_id: UUID,
    section_data: SectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Add a section to a form."""
    form = await db.get(ClinicalForm, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    section = FormSection(
        form_id=form_id,
        title_key=section_data.title_key,
        bloque=section_data.bloque,
        order_index=section_data.order_index
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)
    
    return SectionResponse(
        section_id=section.section_id,
        title_key=section.title_key,
        bloque=section.bloque,
        order_index=section.order_index,
        questions=[]
    )


@router.put("/sections/{section_id}", response_model=SectionResponse)
async def update_section(
    section_id: UUID,
    section_data: SectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update a section."""
    result = await db.execute(
        select(FormSection)
        .where(FormSection.section_id == section_id)
        .options(selectinload(FormSection.questions).selectinload(FormQuestion.options))
    )
    section = result.scalar()
    
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    update_data = section_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(section, field, value)
    
    await db.commit()
    await db.refresh(section)
    
    return section


@router.delete("/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(
    section_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete a section and all its questions."""
    section = await db.get(FormSection, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    await db.delete(section)
    await db.commit()


# =============================================================================
# QUESTION ENDPOINTS
# =============================================================================

@router.post("/sections/{section_id}/questions", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
async def create_question(
    section_id: UUID,
    question_data: QuestionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Add a question to a section."""
    try:
        section = await db.get(FormSection, section_id)
        if not section:
            raise HTTPException(status_code=404, detail="Section not found")
        
        question = FormQuestion(
            section_id=section_id,
            id_pregunta=question_data.id_pregunta,
            variable_name=question_data.variable_name,
            data_key=question_data.data_key,
            text_key=question_data.text_key,
            type=question_data.type,
            value_type=question_data.value_type,
            score_mode=question_data.score_mode,
            show_if=question_data.show_if,
            help_text=question_data.help_text,
            placeholder=question_data.placeholder,
            ui_hint=question_data.ui_hint,
            is_required=question_data.is_required,
            order_index=question_data.order_index
        )
        db.add(question)
        await db.flush()
        
        options = []
        if question_data.options:
            for opt_data in question_data.options:
                option = AnswerOption(
                    question_id=question.question_id,
                    value=opt_data.value,
                    label_key=opt_data.label_key,
                    score=opt_data.score,
                    order_index=opt_data.order_index
                )
                db.add(option)
                options.append(option)
        
        await db.commit()
        await db.refresh(question)
        
        return QuestionResponse(
            question_id=question.question_id,
            id_pregunta=question.id_pregunta,
            variable_name=question.variable_name,
            data_key=question.data_key,
            text_key=question.text_key,
            type=question.type,
            value_type=question.value_type,
            score_mode=question.score_mode,
            show_if=question.show_if,
            help_text=question.help_text,
            placeholder=question.placeholder,
            ui_hint=question.ui_hint,
            is_required=question.is_required,
            order_index=question.order_index,
            options=[OptionResponse(
                option_id=o.option_id,
                value=o.value,
                label_key=o.label_key,
                score=o.score,
                order_index=o.order_index
            ) for o in options]
        )
    except Exception as e:
        # Log error in production
        print(f"Error creating question: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating question: {str(e)}"
        )


@router.put("/questions/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: UUID,
    question_data: QuestionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update a question."""
    result = await db.execute(
        select(FormQuestion)
        .where(FormQuestion.question_id == question_id)
        .options(selectinload(FormQuestion.options))
    )
    question = result.scalar()
    
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    update_data = question_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(question, field, value)
    
    await db.commit()
    await db.refresh(question)
    
    return question


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete a question."""
    question = await db.get(FormQuestion, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    await db.delete(question)
    await db.commit()


# =============================================================================
# OPTION ENDPOINTS
# =============================================================================

@router.post("/questions/{question_id}/options", response_model=OptionResponse, status_code=status.HTTP_201_CREATED)
async def create_option(
    question_id: UUID,
    option_data: OptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Add an option."""
    question = await db.get(FormQuestion, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    option = AnswerOption(
        question_id=question_id,
        value=option_data.value,
        label_key=option_data.label_key,
        score=option_data.score,
        context_rules=option_data.context_rules,
        order_index=option_data.order_index
    )
    db.add(option)
    await db.commit()
    await db.refresh(option)
    
    return option


@router.put("/options/{option_id}", response_model=OptionResponse)
async def update_option(
    option_id: UUID,
    option_data: OptionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update an option."""
    option = await db.get(AnswerOption, option_id)
    if not option:
        raise HTTPException(status_code=404, detail="Option not found")
    
    update_data = option_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(option, field, value)
    
    await db.commit()
    await db.refresh(option)
    
    return option


@router.delete("/options/{option_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_option(
    option_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete an option."""
    option = await db.get(AnswerOption, option_id)
    if not option:
        raise HTTPException(status_code=404, detail="Option not found")
    
    await db.delete(option)
    await db.commit()


# =============================================================================
# SCORING RULE ENDPOINTS
# =============================================================================

@router.post("/forms/{form_id}/rules", response_model=ScoringRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_scoring_rule(
    form_id: UUID,
    rule_data: ScoringRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Add a scoring rule."""
    form = await db.get(ClinicalForm, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    rule = ScoringRule(
        form_id=form_id,
        variable_name=rule_data.variable_name,
        formula=rule_data.formula,
        interpretation_ranges=rule_data.interpretation_ranges,
        alert_condition=rule_data.alert_condition,
        alert_type=rule_data.alert_type,
        target_id=rule_data.target_id,
        order_index=rule_data.order_index
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    
    return rule


@router.put("/rules/{rule_id}", response_model=ScoringRuleResponse)
async def update_scoring_rule(
    rule_id: UUID,
    rule_data: ScoringRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update a scoring rule."""
    rule = await db.get(ScoringRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Scoring rule not found")
    
    update_data = rule_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)
    
    await db.commit()
    await db.refresh(rule)
    
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scoring_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete a scoring rule."""
    rule = await db.get(ScoringRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Scoring rule not found")
    
# =============================================================================
# SCORING SIMULATION
# =============================================================================

from app.services.scoring import ScoringEngine
from typing import List, Optional

class SimulationRequest(BaseModel):
    answers: Dict[str, Any]  # Key=data_key (e.g., "frecuencia": 3)
    target_ids: Optional[List[UUID]] = None # Context for scoring

class SimulationResponse(BaseModel):
    scores: Dict[str, Any]
    alerts: List[str]  # Just messages for simulation

@router.post("/forms/{form_id}/simulate", response_model=SimulationResponse)
async def simulate_scoring(
    form_id: UUID,
    sim_data: SimulationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Test the scoring logic of a form with provided dummy answers.
    Does not save anything to DB.
    """
    try:
        # 1. Fetch Form Rules
        form = await db.execute(
            select(ClinicalForm)
            .where(ClinicalForm.form_id == form_id)
            .options(
                selectinload(ClinicalForm.scoring_rules),
                selectinload(ClinicalForm.sections)
                .selectinload(FormSection.questions)
                .selectinload(FormQuestion.options)
            )
        )
        form = form.scalar()
        
        if not form:
            raise HTTPException(status_code=404, detail="Form not found")
            
        # 1.5. Resolve Raw Answers to Scores
        # Helper to map data_key -> Question
        questions_map = {}
        for section in form.sections:
            for q in section.questions:
                if q.data_key:
                    questions_map[q.data_key] = q
        
        resolved_context = {}
        for key, raw_val in sim_data.answers.items():
            if key in questions_map:
                q = questions_map[key]
                if q.score_mode == ScoreMode.OPTION_SCORE:
                    # Find option
                    # raw_val should match option.value
                    found = False
                    for opt in q.options:
                        if opt.value == str(raw_val):
                             resolved_context[key] = opt.score
                    selected_opt = next((o for o in q.options if o.value == str(raw_val)), None)
                    if selected_opt:
                        # Use Engine to resolve score with context
                        resolved_score = engine.resolve_answer_score(selected_opt, target_ids_str)
                        resolved_context[key] = resolved_score
                    else:
                        resolved_context[key] = 0
                elif q.score_mode == ScoreMode.VALUE_AS_SCORE:
                    try:
                        resolved_context[key] = float(raw_val)
                    except:
                        resolved_context[key] = 0
                else:
                    # Default: pass raw value (e.g. for logic)
                    resolved_context[key] = raw_val
            else:
                 # Allow passing direct context variables that aren't answers
                 try:
                    resolved_context[key] = float(raw_val)
                 except:
                    resolved_context[key] = raw_val

        # 2. Run Scoring Engine
        engine = ScoringEngine()
        # Convert UUIDs to strings for the engine
        target_ids_str = [str(t) for t in (sim_data.target_ids or [])]
        scores, alert_results = engine.process_rules(form.scoring_rules, resolved_context, user_target_ids=target_ids_str)
        
        # 3. Format Response
        return SimulationResponse(
            scores=scores,
            alerts=[f"[{a.level.upper()}] {a.message}" for a in alert_results]
        )
    except Exception as e:
        import traceback
        print(f"SIMULATION ERROR: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
