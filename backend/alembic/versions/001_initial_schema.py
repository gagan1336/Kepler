"""Initial schema — all 8 tables

Revision ID: 001
Revises: 
Create Date: 2025-01-01 00:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgcrypto for gen_random_uuid()
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.Text, nullable=True),
        sa.Column("plan", sa.String(20), nullable=False, server_default="free"),
        sa.Column("razorpay_subscription_id", sa.String(255), nullable=True),
        sa.Column("telegram_id", sa.String(100), nullable=True),
        sa.Column("trial_end_date", sa.DateTime, nullable=True),
        sa.Column("google_id", sa.String(255), nullable=True, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "daily_digests",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("date", sa.Date, nullable=False, unique=True),
        sa.Column("items", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("market_mood", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="published"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_daily_digests_date", "daily_digests", ["date"])

    op.create_table(
        "breakout_watchlist",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("setup_description", sa.Text, nullable=True),
        sa.Column("technical_data", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_breakout_watchlist_date", "breakout_watchlist", ["date"])

    op.create_table(
        "sector_reports",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("sector_name", sa.String(100), nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_sector_reports_date", "sector_reports", ["date"])

    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False),
        sa.Column("razorpay_subscription_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("start_date", sa.DateTime, nullable=True),
        sa.Column("end_date", sa.DateTime, nullable=True),
        sa.Column("invoice_url", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_table(
        "content_log",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("content_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("viewed_at", sa.DateTime, nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_table(
        "ipo_briefs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("open_date", sa.Date, nullable=True),
        sa.Column("close_date", sa.Date, nullable=True),
        sa.Column("price_band", sa.String(50), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_table(
        "deep_dives",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("tier", sa.String(20), nullable=False, server_default="elite"),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_table("deep_dives")
    op.drop_table("ipo_briefs")
    op.drop_table("content_log")
    op.drop_table("subscriptions")
    op.drop_index("ix_sector_reports_date", "sector_reports")
    op.drop_table("sector_reports")
    op.drop_index("ix_breakout_watchlist_date", "breakout_watchlist")
    op.drop_table("breakout_watchlist")
    op.drop_index("ix_daily_digests_date", "daily_digests")
    op.drop_table("daily_digests")
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
