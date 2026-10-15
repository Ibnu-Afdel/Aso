"""create users, password_reset_tokens, sessions and failed_jobs tables

Revision ID: 25d246f4b11c
Revises:
Create Date: 2026-10-15 22:47:39
"""

import sqlalchemy as sa
from alembic import op

revision = '25d246f4b11c'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column("remember_token", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "password_reset_tokens",
        sa.Column("email", sa.String(length=255), primary_key=True),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True, index=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("last_activity", sa.Integer(), nullable=False, index=True),
    )
    op.create_table(
        "failed_jobs",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("connection", sa.String(length=255), nullable=False),
        sa.Column("queue", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("exception", sa.Text(), nullable=False),
        sa.Column("failed_at", sa.String(length=40), nullable=False),
        sa.UniqueConstraint("uuid"),
    )


def downgrade() -> None:
    op.drop_table("failed_jobs")
    op.drop_table("sessions")
    op.drop_table("password_reset_tokens")
    op.drop_table("users")
