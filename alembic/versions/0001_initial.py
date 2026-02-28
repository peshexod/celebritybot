"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-02-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


order_status = postgresql.ENUM(
    "pending_payment",
    "paid",
    "generating_audio",
    "generating_video",
    "completed",
    "failed",
    "retrying",
    "refunded",
    name="orderstatus",
    create_type=False,
)
payment_status = postgresql.ENUM("pending", "succeeded", "refunded", "failed", name="paymentstatus", create_type=False)
platform_enum = postgresql.ENUM("telegram", "vk", name="platform", create_type=False)


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE orderstatus AS ENUM (
                'pending_payment', 'paid', 'generating_audio', 'generating_video',
                'completed', 'failed', 'retrying', 'refunded'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE paymentstatus AS ENUM ('pending', 'succeeded', 'refunded', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE platform AS ENUM ('telegram', 'vk');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.Integer(), nullable=True, unique=True),
        sa.Column("vk_id", sa.Integer(), nullable=True, unique=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "characters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("preview_image_path", sa.String(length=500), nullable=False),
        sa.Column("elevenlabs_voice_id", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "character_creatives",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_path", sa.String(length=500), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("characters.id"), nullable=True),
        sa.Column("creative_id", sa.Integer(), sa.ForeignKey("character_creatives.id"), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", order_status, nullable=False),
        sa.Column("payment_id", sa.String(length=128), nullable=True),
        sa.Column("runpod_job_id", sa.String(length=128), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("yookassa_payment_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", payment_status, nullable=False),
        sa.Column("refund_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("refunded_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("orders")
    op.drop_table("character_creatives")
    op.drop_table("characters")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS paymentstatus")
    op.execute("DROP TYPE IF EXISTS orderstatus")
    op.execute("DROP TYPE IF EXISTS platform")
