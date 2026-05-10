"""
Clinical Forms Engine - Models
Version 2.0: Full dynamic questionnaire system with scoring and alerts

This module defines the database models for the clinical questionnaire system,
supporting dynamic form creation, conditional logic, weighted scoring, and alerts.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, Integer, Text, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base
import uuid
from datetime import datetime
import enum


# =============================================================================
# ENUMS
# =============================================================================

class TargetType(str, enum.Enum):
    """Defines who can see/access a form based on their profile."""
    TODAS = "todas"
    EMBARAZADAS = "embarazadas"
    POST_PARTO = "post_parto"
    MENOPAUSIA = "menopausia"
    LACTANCIA = "lactancia"
    DEPORTISTA = "deportista"


class FrecuenciaType(str, enum.Enum):
    """Defines how often a form reappears after completion."""
    UNICA_VEZ = "unica_vez"
    DIARIO = "diario"
    SEMANAL = "semanal"
    MENSUAL = "mensual"
    A_DEMANDA = "a_demanda"


class DisparadorType(str, enum.Enum):
    """Defines when a form first appears to the user."""
    AL_REGISTRO = "al_registro"
    BLOQUEANTE = "bloqueante"
    MANUAL = "manual"
    DIA_7 = "dia_7"
    DIA_30 = "dia_30"


class QuestionType(str, enum.Enum):
    """Defines the input type for a question."""
    single = "single"
    multi = "multi"
    dropdown = "dropdown"
    scale = "scale"
    ranking = "ranking"
    date = "date"
    text = "text"
    paragraph = "paragraph"
    info = "info"


class ValueType(str, enum.Enum):
    """Defines how the answer value is stored."""
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    STRING = "string"
    DATE = "date"
    ARRAY = "array"


class ScoreMode(str, enum.Enum):
    """Defines how a question contributes to the total score."""
    NONE = "none"
    OPTION_SCORE = "option_score"
    VALUE_AS_SCORE = "value_as_score"
    FORMULA = "formula"


class UIHint(str, enum.Enum):
    """UI rendering hints for the frontend."""
    NUMERIC_KEYBOARD = "numeric_keyboard"
    SEARCHABLE_DROPDOWN = "searchable_dropdown"
    SLIDER_TICKS = "slider_ticks"
    TOP3_RANKING = "top3_ranking"
    YES_NO_BUTTONS = "yes_no_buttons"
    CHIPS_MULTI = "chips_multi"


class AlertType(str, enum.Enum):
    """Types of clinical alerts that can be triggered."""
    DERIVACION_CLINICA = "derivacion_clinica"
    ACTIVAR_PLAN = "activar_plan"
    SEGUIMIENTO = "seguimiento"


class FormStatus(str, enum.Enum):
    """Lifecycle status of a form."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


# =============================================================================
# TARGETING
# =============================================================================

class Target(Base):
    """
    Specific user segment that a form is designed for.
    E.g., "Pregnant", "Post-Partum", "Athlete", "Post-Menopausal".
    """
    __tablename__ = "targets"
    
    target_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String, unique=True, nullable=False, index=True) # e.g. "embarazadas"
    name = Column(String, nullable=False) # e.g. "Embarazadas"
    description = Column(String)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    forms = relationship("ClinicalForm", secondary="form_targets", back_populates="targets")
    profiles = relationship("Profile", secondary="profile_targets", back_populates="targets")


class FormTarget(Base):
    """
    Many-to-Many link between Forms and Targets.
    Allows a single form to target multiple user segments.
    """
    __tablename__ = "form_targets"
    
    form_id = Column(UUID(as_uuid=True), ForeignKey("clinical_forms.form_id", ondelete="CASCADE"), primary_key=True)
    target_id = Column(UUID(as_uuid=True), ForeignKey("targets.target_id", ondelete="CASCADE"), primary_key=True)


class ProfileTarget(Base):
    """
    Many-to-Many link between User Profiles and Clinical Targets (Tags).
    Used for automated segmentation (e.g. TagAutomationService).
    """
    __tablename__ = "profile_targets"
    
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.profile_id", ondelete="CASCADE"), primary_key=True)
    target_id = Column(UUID(as_uuid=True), ForeignKey("targets.target_id", ondelete="CASCADE"), primary_key=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)


# =============================================================================
# FORM STRUCTURE MODELS
# =============================================================================

class ClinicalForm(Base):
    """
    Master form definition.
    Contains metadata about the questionnaire including targeting and scheduling.
    """
    __tablename__ = "clinical_forms"
    
    form_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String, unique=True, nullable=False, index=True)
    title_key = Column(String)  # Translation key for title
    description_key = Column(String)  # Translation key for description
    version = Column(Integer, default=1)
    status = Column(Enum(FormStatus), default=FormStatus.DRAFT)
    is_active = Column(Boolean, default=True)
    
    # Targeting & Scheduling
    # target = Column(Enum(TargetType), default=TargetType.TODAS) # Deprecated by targets relation
    frecuencia = Column(Enum(FrecuenciaType), default=FrecuenciaType.UNICA_VEZ)
    disparador = Column(Enum(DisparadorType), default=DisparadorType.AL_REGISTRO)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    targets = relationship("Target", secondary="form_targets", back_populates="forms")
    sections = relationship("FormSection", back_populates="form", cascade="all, delete-orphan", order_by="FormSection.order_index")
    scoring_rules = relationship("ScoringRule", back_populates="form", cascade="all, delete-orphan", order_by="ScoringRule.order_index")
    submissions = relationship("UserSubmission", back_populates="form")


class FormSection(Base):
    """
    Logical grouping of questions within a form.
    Used for visual organization and clinical categorization.
    """
    __tablename__ = "form_sections"
    
    section_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id = Column(UUID(as_uuid=True), ForeignKey("clinical_forms.form_id", ondelete="CASCADE"), nullable=False)
    title_key = Column(String)  # Translation key
    bloque = Column(String)  # Clinical category grouping (e.g., "CONTROL_Y_CONTINENCIA")
    order_index = Column(Integer, default=0)
    
    # Relationships
    form = relationship("ClinicalForm", back_populates="sections")
    questions = relationship("FormQuestion", back_populates="section", cascade="all, delete-orphan", order_by="FormQuestion.order_index")


class FormQuestion(Base):
    """
    Individual question within a section.
    Contains all configuration for rendering, validation, and scoring.
    """
    __tablename__ = "form_questions"
    
    question_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    section_id = Column(UUID(as_uuid=True), ForeignKey("form_sections.section_id", ondelete="CASCADE"), nullable=False)
    
    # Nomenclature / Identity
    id_pregunta = Column(String, index=True)  # Visible code: URIN01_DISPARADORA, URIN02_ICIQ_FRECUENCIA
    variable_name = Column(String)  # Human readable: "Disparadora", "ICIQ Frecuencia"
    data_key = Column(String, index=True)  # For formulas/API: iciq_frecuencia, urinaria_screening
    text_key = Column(String)  # Translation key for question text
    
    # Type & Storage
    type = Column(Enum(QuestionType), nullable=False)
    value_type = Column(Enum(ValueType), default=ValueType.STRING)
    score_mode = Column(Enum(ScoreMode), default=ScoreMode.NONE)
    
    # Conditional Logic
    show_if = Column(Text)  # Expression: "Q1 == 'si' AND Q2 > 5"
    
    # UI Configuration
    help_text = Column(Text)
    placeholder = Column(String)
    ui_hint = Column(Enum(UIHint))
    
    # Validation
    is_required = Column(Boolean, default=False)
    validation_rules = Column(JSONB)  # Future: {"type": "regex", "pattern": "..."}
    
    # Legacy config (for backwards compatibility)
    config = Column(JSONB)
    
    order_index = Column(Integer, default=0)
    
    # Relationships
    section = relationship("FormSection", back_populates="questions")
    options = relationship("AnswerOption", back_populates="question", cascade="all, delete-orphan", order_by="AnswerOption.order_index")


class AnswerOption(Base):
    """
    Individual option for SINGLE, MULTI, DROPDOWN, RANKING questions.
    Includes scoring weight for each option.
    """
    __tablename__ = "answer_options"
    
    option_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("form_questions.question_id", ondelete="CASCADE"), nullable=False)
    
    value = Column(String, nullable=False)  # Internal value (e.g., "nunca")
    label_key = Column(String)  # Translation key for display
    score = Column(Integer, default=0)  # Weight for scoring
    
    # Granular Scoring (Phase 11)
    # List of overrides: [{"conditions": {"targets": ["athlete"]}, "override_score": 5}]
    context_rules = Column(JSONB)
    
    order_index = Column(Integer, default=0)
    
    # Relationships
    question = relationship("FormQuestion", back_populates="options")


# =============================================================================
# SCORING & ALERTS
# =============================================================================

class ScoringRule(Base):
    """
    Defines scoring formulas and alert conditions for a form.
    Evaluated after form submission to calculate totals and trigger alerts.
    """
    __tablename__ = "scoring_rules"
    
    rule_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id = Column(UUID(as_uuid=True), ForeignKey("clinical_forms.form_id", ondelete="CASCADE"), nullable=False)
    
    # What this rule calculates
    variable_name = Column(String, nullable=False)  # e.g., "iciq_total"
    formula = Column(Text)  # e.g., "iciq_frecuencia + iciq_cantidad + iciq_impacto"
    
    # Interpretation ranges (optional)
    interpretation_ranges = Column(JSONB)  # e.g., {"0-5": "Leve", "6-10": "Moderado", ">10": "Severo"}
    
    # Alert configuration
    alert_condition = Column(Text)  # e.g., "value >= 10"
    alert_type = Column(Enum(AlertType))
    
    # Context-Aware Scoring (Phase 10)
    target_id = Column(UUID(as_uuid=True), ForeignKey("targets.target_id", ondelete="SET NULL"), nullable=True)
    
    order_index = Column(Integer, default=0)
    
    # Relationships
    form = relationship("ClinicalForm", back_populates="scoring_rules")
    target = relationship("Target")
    alerts = relationship("ClinicalAlert", back_populates="rule")


class ClinicalAlert(Base):
    """
    Record of alerts triggered by scoring rules.
    Tracks visibility across different apps (mobile, admin).
    """
    __tablename__ = "clinical_alerts"
    
    alert_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("user_submissions.submission_id"), nullable=False)
    rule_id = Column(UUID(as_uuid=True), ForeignKey("scoring_rules.rule_id"), nullable=False)
    
    alert_type = Column(Enum(AlertType), nullable=False)
    triggered_value = Column(Float)  # The value that triggered the alert
    
    # Timestamps
    triggered_at = Column(DateTime, default=datetime.utcnow)
    
    # Visibility tracking
    is_viewed_admin = Column(Boolean, default=False)  # Admin saw it
    is_shown_to_user = Column(Boolean, default=False)  # Shown in mobile app
    resolved_at = Column(DateTime)  # When/if resolved
    
    # Relationships
    rule = relationship("ScoringRule", back_populates="alerts")
    submission = relationship("UserSubmission", back_populates="alerts")


# =============================================================================
# USER RESPONSES
# =============================================================================

class UserSubmission(Base):
    """
    Instance of a user completing a form.
    Links to the specific form version for historical accuracy.
    """
    __tablename__ = "user_submissions"
    
    submission_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    form_id = Column(UUID(as_uuid=True), ForeignKey("clinical_forms.form_id"), nullable=False)
    form_version = Column(Integer)  # Snapshot of form version at submission time
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)  # Null until finalized
    
    # Calculated results
    total_score = Column(Float)
    score_interpretation = Column(String)  # e.g., "Moderado"
    calculated_values = Column(JSONB)  # All calculated variables
    
    # Relationships
    user = relationship("User", back_populates="submissions")
    form = relationship("ClinicalForm", back_populates="submissions")
    answers = relationship("SubmissionAnswer", back_populates="submission", cascade="all, delete-orphan")
    alerts = relationship("ClinicalAlert", back_populates="submission")


class SubmissionAnswer(Base):
    """
    Individual answer to a question within a submission.
    Stores both the raw value and calculated score.
    """
    __tablename__ = "submission_answers"
    
    answer_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("user_submissions.submission_id", ondelete="CASCADE"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("form_questions.question_id"), nullable=False)
    
    value = Column(JSONB)  # The actual answer
    score = Column(Integer, default=0)  # Calculated score for this answer
    
    # Relationships
    submission = relationship("UserSubmission", back_populates="answers")


# =============================================================================
# CLINICAL SNAPSHOT (unchanged from original)
# =============================================================================

class ClinicalSnapshot(Base):
    """
    Cached aggregation of a user's clinical state.
    Used for quick access by AI/chat without re-querying all submissions.
    """
    __tablename__ = "clinical_snapshots"
    
    snapshot_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    last_updated = Column(DateTime, default=datetime.utcnow)
    data = Column(JSONB)


# =============================================================================
# LEGACY COMPATIBILITY (to be removed after migration)
# =============================================================================

class ScoringLogic(Base):
    """
    DEPRECATED: Use ScoringRule instead.
    Kept for backwards compatibility during migration.
    """
    __tablename__ = "scoring_logic"
    
    rule_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id = Column(UUID(as_uuid=True), ForeignKey("clinical_forms.form_id"))
    condition_expression = Column(Text)
    outcome_score = Column(Integer)
    outcome_tag = Column(String)
