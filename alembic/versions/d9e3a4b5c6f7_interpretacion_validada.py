"""scoring_rule: distinguir una interpretación validada de una provisoria

Los rangos que traducen un puntaje a su etiqueta clínica ("Leve", "Moderado",
"Severo") son criterio médico, no aritmética. Hasta ahora no había forma de
saber si los cargados en una regla habían sido validados por la clínica o eran
un borrador razonable: la médica abre el panel, ve "Severo" y no tiene cómo
distinguir una cosa de la otra.

La bandera nace en falso a propósito, incluida para lo ya cargado. Marcar algo
como validado tiene que ser un acto deliberado de quien puede validarlo.

Mientras una interpretación siga siendo provisoria puede mostrarse —con su
advertencia— pero no debe alimentar decisiones clínicas automáticas.

Revision ID: d9e3a4b5c6f7
Revises: c8d2f3a4b5e6
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d9e3a4b5c6f7"
down_revision: Union[str, None] = "c8d2f3a4b5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scoring_rules",
        sa.Column(
            "interpretation_validated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("scoring_rules", "interpretation_validated")
