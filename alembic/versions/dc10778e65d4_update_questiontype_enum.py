"""update_questiontype_enum

Revision ID: dc10778e65d4
Revises: dfb82dfaebb0
Create Date: 2026-01-19 11:28:44.123456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc10778e65d4'
down_revision: Union[str, None] = 'dfb82dfaebb0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new values to questiontype enum
    # We must commit before each ALTER TYPE execution because PostgreSQL requires it outside a transaction block 
    # for concurrent safety, OR we rely on Alembic's transaction handling. 
    # 'ALTER TYPE ... ADD VALUE' cannot run inside a transaction block generally in older PG, 
    # but since PG 12 it can if the new value is not used in the same transaction.
    # We will use execute with isolation level validation if needed, but op.execute simply runs sql.
    
    # We wrap in verification blocks to avoid errors if re-run
    
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'single'")
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'multi'")
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'dropdown'")
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'ranking'")
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'date'")
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'paragraph'")
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'info'")
    
    # Note: 'scale' and 'text' might already exist or be uppercase. 
    # The python enum uses 'scale' (lowercase). DB has 'SCALE' (uppercase).
    # This is a conflict. We should probably add the lowercase versions too.
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'scale'")
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'text'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum easily.
    # We typically ignore downgrade for enum additions in dev.
    pass
