# PelvIA Backend: Esquema de Base de Datos

*Este documento detalla los modelos de SQLAlchemy y sus relaciones para evitar errores de integridad o consultas N+1.*

## 📐 Diagrama Lógico (Resumen)
- `ClinicalForm` (1) <-> (N) `FormSection`
- `FormSection` (1) <-> (N) `FormQuestion`
- `FormQuestion` (1) <-> (N) `AnswerOption`
- `ClinicalForm` (1) <-> (N) `ScoringRule`
- `ClinicalForm` (M) <-> (N) `Target` (via `form_targets` table)

## 📌 Modelos Críticos

### ClinicalForm
- `code`: String único (ID para URLs).
- `status`: Enum (DRAFT, PUBLISHED).
- `frecuencia`: Enum (UNICA_VEZ, DIARIO, etc).

### FormQuestion
- `data_key`: El identificador usado en fórmulas de scoring.
- `score_mode`: Define cómo se calcula el punto de la pregunta.

[Completar con detalles de campos y llaves foráneas]
