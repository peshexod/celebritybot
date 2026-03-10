"""Add chatterbox_job_id, sonic_job_id, video_file_id and attempt counters

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-09

"""

from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002_creative_tg_file_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('chatterbox_job_id', sa.String(64), nullable=True))
    op.add_column('orders', sa.Column('chatterbox_attempt', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('orders', sa.Column('sonic_job_id', sa.String(64), nullable=True))
    op.add_column('orders', sa.Column('sonic_attempt', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('orders', sa.Column('video_file_id', sa.String(256), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'video_file_id')
    op.drop_column('orders', 'sonic_attempt')
    op.drop_column('orders', 'sonic_job_id')
    op.drop_column('orders', 'chatterbox_attempt')
    op.drop_column('orders', 'chatterbox_job_id')
