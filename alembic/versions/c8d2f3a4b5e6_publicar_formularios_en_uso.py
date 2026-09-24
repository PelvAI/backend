"""publicar los formularios que ya estaban en uso

Hasta ahora la aplicación mostraba todo formulario con is_active verdadero, sin
mirar su estado, de modo que un borrador quedaba visible para las usuarias
apenas se creaba y el acto de publicar no existía (F2). Al empezar a filtrar
por estado, todo lo creado desde el panel —que nace en DRAFT— desaparecería de
un día para el otro.

Esta migración promueve a ACTIVE lo que hoy está efectivamente en uso, para que
el cambio de comportamiento no le quite nada a nadie:

  * Se promueve todo formulario activo, en borrador y con al menos una
    pregunta. Es lo que las usuarias ya veían y podían responder.
  * Se deja en borrador el que no tiene ninguna pregunta. Aparecía en la lista
    y no se podía responder: que desaparezca es la corrección, no una pérdida.
  * No se toca nada archivado.

Los cuestionarios sembrados (ICIQ-SF y PFDI-20) ya nacen ACTIVE, así que no
dependen de esto.

Revision ID: c8d2f3a4b5e6
Revises: b7c1e2f3a4d5
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8d2f3a4b5e6"
down_revision: Union[str, None] = "b7c1e2f3a4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PROMOVER = """
UPDATE clinical_forms
   SET status = 'ACTIVE'
 WHERE status = 'DRAFT'
   AND is_active = true
   AND EXISTS (
       SELECT 1
         FROM form_sections s
         JOIN form_questions q ON q.section_id = s.section_id
        WHERE s.form_id = clinical_forms.form_id
   )
"""


def upgrade() -> None:
    resultado = op.get_bind().execute(sa.text(PROMOVER))
    print(f"[c8d2f3a4b5e6] formularios promovidos a ACTIVE: {resultado.rowcount}")


def downgrade() -> None:
    # No hay forma de distinguir después cuáles habían sido promovidos por esta
    # migración y cuáles se publicaron a mano, así que revertir devolvería a
    # borrador cosas que alguien publicó a propósito. Se deja deliberadamente
    # sin efecto: el estado de un formulario es dato de negocio, no de esquema.
    pass
