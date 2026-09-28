"""scoring_rule: marcar cuál regla produce el puntaje total

Hasta ahora el puntaje total de una evaluación se elegía con una heurística que
buscaba las variables 'iciq_total' y 'total_score' por nombre, de modo que
cualquier cuestionario que no las nombrara así quedaba con puntaje cero y sin
aviso (F17). Con esta bandera el formulario declara explícitamente cuál de sus
reglas es el total.

La heurística se conserva como respaldo para los formularios ya cargados, que
no tienen ninguna regla marcada.

Revision ID: b7c1e2f3a4d5
Revises: a1b2c3d4e5f6
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c1e2f3a4d5"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scoring_rules",
        sa.Column("is_total", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Una alerta disparada por la regla contextual de una opción no proviene de
    # ninguna ScoringRule, así que la columna deja de ser obligatoria. Antes el
    # motor ni siquiera llegaba a generarlas, de modo que la restricción nunca
    # se había puesto a prueba (F16).
    op.alter_column(
        "clinical_alerts", "rule_id", existing_type=sa.UUID(), nullable=True
    )


def downgrade() -> None:
    op.execute("DELETE FROM clinical_alerts WHERE rule_id IS NULL")
    op.alter_column(
        "clinical_alerts", "rule_id", existing_type=sa.UUID(), nullable=False
    )
    op.drop_column("scoring_rules", "is_total")
