"""Add token_usage column to generation_logs

Revision ID: 002
Revises: 001
Create Date: 2026-02-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generation_logs", sa.Column("token_usage", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("generation_logs", "token_usage")
