"""form_sections: archivar en lugar de destruir

Mismo criterio que en preguntas y reglas. Borrar una sección era físico y
arrastraba sus preguntas en cascada; como la clave foránea de las respuestas no
declara ondelete, eliminar una sección con preguntas ya respondidas rompía con
una violación sin manejar (F42).

Revision ID: f2a5b6c7d8e9
Revises: e1f4a5b6c7d8
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a5b6c7d8e9"
down_revision: Union[str, None] = "e1f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "form_sections",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("form_sections", "is_active")
