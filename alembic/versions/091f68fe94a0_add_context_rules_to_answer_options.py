"""add_context_rules_to_answer_options

Revision ID: 091f68fe94a0
Revises: 38969006f6f8
Create Date: 2026-02-09 07:51:22.250581

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '091f68fe94a0'
down_revision: Union[str, None] = '38969006f6f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('answer_options', sa.Column('context_rules', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('answer_options', 'context_rules')
