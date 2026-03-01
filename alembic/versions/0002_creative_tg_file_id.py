"""add telegram_file_id to character_creatives

Revision ID: 0002_creative_tg_file_id
Revises: 0001_initial
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_creative_tg_file_id"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("character_creatives", sa.Column("telegram_file_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("character_creatives", "telegram_file_id")
