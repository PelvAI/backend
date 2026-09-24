from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any, Dict
from app.models.clinical import QuestionType

# --- Question Schemas ---
class OptionResponse(BaseModel):
    option_id: UUID
    value: str
    label_key: Optional[str] = None
    score: int = 0
    order_index: int = 0
    model_config = ConfigDict(from_attributes=True)

class QuestionResponse(BaseModel):
    question_id: UUID
    type: QuestionType
    variable_name: Optional[str] = None
    data_key: Optional[str] = None
    text_key: Optional[str] = None
    ui_hint: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    order_index: int = 0
    options: List[OptionResponse] = []
    model_config = ConfigDict(from_attributes=True)

class SectionResponse(BaseModel):
    section_id: UUID
    title_key: Optional[str] = None
    # Agrupación clínica de la sección (URIN, PROL...). La app la necesita para
    # poder mostrar los resultados por bloque, y no se exponía.
    bloque: Optional[str] = None
    order_index: int
    questions: List[QuestionResponse]
    model_config = ConfigDict(from_attributes=True)

# --- Target Schemas ---
class TargetResponse(BaseModel):
    target_id: UUID
    code: str
    name: str
    description: Optional[str] = None
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

class TargetCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None

class TargetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

# --- Scoring Schemas ---
class ScoringRuleResponse(BaseModel):
    rule_id: UUID
    variable_name: str
    formula: Optional[str] = None
    interpretation_ranges: Optional[Dict[str, Any]] = None
    alert_condition: Optional[str] = None
    alert_type: Optional[str] = None
    order_index: int = 0
    model_config = ConfigDict(from_attributes=True)

class FormResponse(BaseModel):
    form_id: UUID
    code: str
    title_key: Optional[str] = None
    description_key: Optional[str] = None
    version: int
    targets: List[TargetResponse] = []
    status: str
    is_active: bool
    frecuencia: Optional[str] = None
    disparador: Optional[str] = None
    sections: List[SectionResponse] = []
    scoring_rules: List[ScoringRuleResponse] = []

    # Cuándo le corresponde este cuestionario a quien pregunta. Antes el
    # listado devolvía todo lo publicado sin mirar si ya se había respondido,
    # así que la app no podía distinguir lo pendiente de lo hecho (F5, F25).
    availability: str = "disponible"
    last_completed_at: Optional[datetime] = None
    next_available_at: Optional[datetime] = None
    is_blocking: bool = False

    model_config = ConfigDict(from_attributes=True)

# --- Submission Schemas ---
class AnswerCreate(BaseModel):
    question_id: UUID
    value: Any

class SubmissionCreate(BaseModel):
    form_id: UUID

class SubmissionUpdate(BaseModel):
    answers: List[AnswerCreate]

class SubmissionResponse(BaseModel):
    submission_id: UUID
    form_id: UUID
    created_at: datetime
    completed_at: Optional[datetime] = None
    total_score: Optional[float] = None
    # La interpretación clínica del puntaje ("Leve", "Moderado", "Severo"),
    # derivada de los rangos que define el formulario. Se persistía en la
    # columna pero nunca se exponía, así que la app no podía mostrarla.
    score_interpretation: Optional[str] = None
    calculated_values: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(from_attributes=True)

class ClinicalSnapshotResponse(BaseModel):
    snapshot_id: UUID
    last_updated: datetime
    data: Dict[str, Any]
    model_config = ConfigDict(from_attributes=True)
