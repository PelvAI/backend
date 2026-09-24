"""integridad del histórico clínico

Tres arreglos sobre los datos y sus restricciones:

1. Respuestas duplicadas. Guardar el borrador insertaba filas nuevas en vez de
   actualizar, así que corregir una respuesta dejaba las dos versiones y el
   puntaje pasaba a depender del orden del iterado. Se deduplica lo existente
   —conservando la última escrita— y se agrega la restricción única que impide
   que vuelva a pasar. Con la restricción, el arreglo del endpoint deja de ser
   una promesa y pasa a ser algo que la base garantiza.

2. Borrado de preguntas y reglas ya usadas. Hoy es borrado físico y las claves
   foráneas que las referencian no declaran ondelete, así que eliminar una
   pregunta ya respondida rompe con una violación sin manejar. La bandera
   is_active permite archivarlas conservando la evidencia clínica.

3. La versión del formulario en la evaluación. La columna existía para
   registrar bajo qué versión se respondió y nunca se escribía; se completa lo
   ya cargado con la versión actual del formulario, que es la mejor
   aproximación disponible.

Revision ID: e1f4a5b6c7d8
Revises: d9e3a4b5c6f7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f4a5b6c7d8"
down_revision: Union[str, None] = "d9e3a4b5c6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Conserva la fila escrita más tarde para cada (evaluación, pregunta), que es
# la que el motor ya venía tomando al iterar.
DEDUPLICAR = """
DELETE FROM submission_answers a
 USING submission_answers b
 WHERE a.submission_id = b.submission_id
   AND a.question_id   = b.question_id
   AND a.ctid < b.ctid
"""

COMPLETAR_VERSION = """
UPDATE user_submissions s
   SET form_version = f.version
  FROM clinical_forms f
 WHERE f.form_id = s.form_id
   AND s.form_version IS NULL
"""


def upgrade() -> None:
    bind = op.get_bind()

    borradas = bind.execute(sa.text(DEDUPLICAR)).rowcount
    print(f"[e1f4a5b6c7d8] respuestas duplicadas eliminadas: {borradas}")

    op.create_unique_constraint(
        "uq_submission_answers_submission_question",
        "submission_answers",
        ["submission_id", "question_id"],
    )

    op.add_column(
        "form_questions",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "scoring_rules",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    completadas = bind.execute(sa.text(COMPLETAR_VERSION)).rowcount
    print(f"[e1f4a5b6c7d8] evaluaciones con versión completada: {completadas}")


def downgrade() -> None:
    op.drop_column("scoring_rules", "is_active")
    op.drop_column("form_questions", "is_active")
    op.drop_constraint(
        "uq_submission_answers_submission_question",
        "submission_answers",
        type_="unique",
    )
    # La deduplicación y el completado de versión no se revierten: reconstruir
    # filas duplicadas o volver a vaciar la columna no le devuelve información
    # a nadie.
