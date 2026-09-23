"""Add severity_tier_pcts JSONB column to vaisala_sections

Revision ID: 018_vaisala_severity_tier_pcts
Revises: 017_vaisala_defect_proportions
Create Date: 2026-09-23

Adds nullable JSONB column storing length-weighted tier percentages
(Structural/High/Medium/Low) per section. Computed via MAX-across-tier-members
per interval, same logic as existing structural_pct treatment group.
Independent of treatment group logic; purely display-layer.
Existing rows stay NULL until re-uploaded.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "018_vaisala_severity_tier_pcts"
down_revision = "017_vaisala_defect_proportions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "vaisala_sections",
        sa.Column(
            "severity_tier_pcts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("vaisala_sections", "severity_tier_pcts")
