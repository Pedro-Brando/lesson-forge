"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "year_levels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(20), unique=True, nullable=False),
        sa.Column("title", sa.String(50), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("level_description", sa.Text()),
        sa.Column("band", sa.String(20), nullable=False),
    )

    op.create_table(
        "strands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(20), unique=True, nullable=False),
        sa.Column("title", sa.String(50), unique=True, nullable=False),
    )

    op.create_table(
        "content_descriptors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(20), unique=True, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "year_level_code",
            sa.String(20),
            sa.ForeignKey("year_levels.code"),
            nullable=False,
        ),
        sa.Column(
            "strand_title",
            sa.String(50),
            sa.ForeignKey("strands.title"),
            nullable=False,
        ),
    )

    op.create_table(
        "elaborations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), unique=True, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "content_descriptor_code",
            sa.String(20),
            sa.ForeignKey("content_descriptors.code"),
            nullable=False,
        ),
    )

    op.create_table(
        "achievement_standards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(20), unique=True, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "year_level_code",
            sa.String(20),
            sa.ForeignKey("year_levels.code"),
            nullable=False,
        ),
    )

    op.create_table(
        "teaching_focuses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), unique=True, nullable=False),
        sa.Column("slug", sa.String(50), unique=True, nullable=False),
    )

    op.create_table(
        "resource_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "teaching_focus_slug",
            sa.String(50),
            sa.ForeignKey("teaching_focuses.slug"),
            nullable=False,
        ),
    )

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), unique=True, nullable=False),
        sa.Column(
            "resource_type_slug",
            sa.String(100),
            sa.ForeignKey("resource_types.slug"),
            nullable=True,
        ),
        sa.Column(
            "teaching_focus_slug",
            sa.String(50),
            sa.ForeignKey("teaching_focuses.slug"),
            nullable=True,
        ),
        sa.Column("year_band", sa.String(20), nullable=True),
        sa.Column("template_body", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="0"),
    )

    op.create_table(
        "generation_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("request_payload", JSONB()),
        sa.Column("matched_descriptors", JSONB()),
        sa.Column("routing_decision", JSONB()),
        sa.Column("rag_results", JSONB()),
        sa.Column("selected_template", sa.String(200)),
        sa.Column("resolved_prompt", sa.Text()),
        sa.Column("generated_resource", sa.Text()),
        sa.Column("step_timings", JSONB()),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("generation_logs")
    op.drop_table("prompt_templates")
    op.drop_table("resource_types")
    op.drop_table("teaching_focuses")
    op.drop_table("achievement_standards")
    op.drop_table("elaborations")
    op.drop_table("content_descriptors")
    op.drop_table("strands")
    op.drop_table("year_levels")
