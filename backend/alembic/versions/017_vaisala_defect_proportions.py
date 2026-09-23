"""Add defect_proportions JSONB column to vaisala_sections

Revision ID: 017_vaisala_defect_proportions
Revises: 016_users_is_active
Create Date: 2026-09-23

Adds a nullable JSONB column storing the length-weighted average proportion
(0-1) per defect for each section. Populated on next upload; existing rows
remain NULL and display without per-defect breakdown until re-uploaded.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "017_vaisala_defect_proportions"
down_revision = "016_users_is_active"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "vaisala_sections",
        sa.Column(
            "defect_proportions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("vaisala_sections", "defect_proportions")
