"""Add vaisala_intervals table for raw interval storage (merge scale support)

Revision ID: 008_vaisala_intervals
Revises: 007_vaisala_asset_link
Create Date: 2026-09-14
"""
import sqlalchemy as sa
from alembic import op

revision = "008_vaisala_intervals"
down_revision = "007_vaisala_asset_link"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vaisala_intervals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("survey_id", sa.Integer(), sa.ForeignKey("vaisala_surveys.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_ref", sa.String(), nullable=False),
        sa.Column("road_name", sa.String()),
        sa.Column("net_reference", sa.String()),
        sa.Column("urban_rural", sa.String()),
        sa.Column("road_class", sa.String()),
        sa.Column("from_m", sa.Float()),
        sa.Column("to_m", sa.Float()),
        sa.Column("length_m", sa.Float(), nullable=False),
        sa.Column("interval_score", sa.Float()),
        sa.Column("structural", sa.Float()),
        sa.Column("localised", sa.Float()),
        sa.Column("dressing", sa.Float()),
        sa.Column("micro", sa.Float()),
        sa.Column("alligator", sa.Float()),
        sa.Column("edge", sa.Float()),
        sa.Column("primary_defect", sa.String()),
        sa.Column("primary_defect_contribution", sa.Float()),
        sa.Column("road_surface_condition", sa.Float()),
        sa.Column("road_surface_condition_class", sa.String()),
        sa.Column("asphalt_condition", sa.Float()),
        sa.Column("asphalt_condition_class", sa.String()),
        sa.Column("pas2161_category", sa.String()),
        sa.Column("time_utc", sa.String()),
    )
    op.create_index("ix_vaisala_intervals_survey", "vaisala_intervals", ["survey_id"])
    op.create_index("ix_vaisala_intervals_section", "vaisala_intervals", ["survey_id", "section_ref"])
    op.create_index("ix_vaisala_intervals_score", "vaisala_intervals", ["interval_score"])


def downgrade():
    op.drop_index("ix_vaisala_intervals_score", "vaisala_intervals")
    op.drop_index("ix_vaisala_intervals_section", "vaisala_intervals")
    op.drop_index("ix_vaisala_intervals_survey", "vaisala_intervals")
    op.drop_table("vaisala_intervals")
