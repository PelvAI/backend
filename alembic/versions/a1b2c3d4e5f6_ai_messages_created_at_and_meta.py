"""ai_messages_created_at_and_meta

Revision ID: a1b2c3d4e5f6
Revises: 2c3bfff89328
Create Date: 2026-07-21 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "2c3bfff89328"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_conversations",
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.add_column(
        "ai_messages",
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.add_column(
        "ai_messages",
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "ai_optimizations",
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_column("ai_optimizations", "created_at")
    op.drop_column("ai_messages", "meta")
    op.drop_column("ai_messages", "created_at")
    op.drop_column("ai_conversations", "created_at")
