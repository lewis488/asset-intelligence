"""Add raw Confirm tables: scanner_raw_records, cvi_raw_records, scrim_records

Revision ID: 002_raw_confirm_tables
Revises: 001_initial_tables
Create Date: 2026-06-05
"""
import sqlalchemy as sa
from alembic import op

revision = "002_raw_confirm_tables"
down_revision = "001_initial_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "scanner_raw_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("survey_year", sa.Integer()),
        sa.Column("survey_date", sa.DateTime()),
        sa.Column("survey_number", sa.String()),
        sa.Column("total_length_m", sa.Float()),
        sa.Column("avg_ci", sa.Float()),
        sa.Column("red_pct", sa.Float()),
        sa.Column("amber_pct", sa.Float()),
        sa.Column("green_pct", sa.Float()),
        sa.Column("max_ci", sa.Float()),
        sa.Column("min_ci", sa.Float()),
        sa.Column("rci_band", sa.String()),
        sa.Column("offset_direction", sa.String()),
        sa.Column("source_file", sa.String()),
        sa.Column("ingested_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "asset_id", "survey_year", "offset_direction",
            name="uq_scanner_raw_asset_year_dir",
        ),
    )

    op.create_table(
        "cvi_raw_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("survey_year", sa.Integer()),
        sa.Column("survey_date", sa.DateTime()),
        sa.Column("survey_name", sa.String()),
        sa.Column("total_length_m", sa.Float()),
        sa.Column("avg_ci_overall", sa.Float()),
        sa.Column("max_ci_structural", sa.Float()),
        sa.Column("max_ci_edge", sa.Float()),
        sa.Column("max_ci_wearingcourse", sa.Float()),
        sa.Column("structural_flagged", sa.Boolean(), server_default="false"),
        sa.Column("edge_flagged", sa.Boolean(), server_default="false"),
        sa.Column("wearingcourse_flagged", sa.Boolean(), server_default="false"),
        sa.Column("any_flagged", sa.Boolean(), server_default="false"),
        sa.Column("pct_length_structural_flagged", sa.Float()),
        sa.Column("pct_length_edge_flagged", sa.Float()),
        sa.Column("pct_length_wc_flagged", sa.Float()),
        sa.Column("source_file", sa.String()),
        sa.Column("ingested_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("asset_id", "survey_year", name="uq_cvi_raw_asset_year"),
    )

    op.create_table(
        "scrim_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("survey_year", sa.Integer()),
        sa.Column("survey_date", sa.DateTime()),
        sa.Column("survey_name", sa.String()),
        sa.Column("survey_number", sa.String()),
        sa.Column("total_sections", sa.Integer()),
        sa.Column("dominant_ilct", sa.String()),
        sa.Column("sfct_threshold", sa.Float()),
        sa.Column("mean_sfc", sa.Float()),
        sa.Column("min_sfc", sa.Float()),
        sa.Column("sections_below_il", sa.Integer()),
        sa.Column("pct_below_il", sa.Float()),
        sa.Column("safety_flagged", sa.Boolean(), server_default="false"),
        sa.Column("worst_xdif", sa.Float()),
        sa.Column("source_file", sa.String()),
        sa.Column("ingested_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("asset_id", "survey_year", name="uq_scrim_asset_year"),
    )


def downgrade():
    op.drop_table("scrim_records")
    op.drop_table("cvi_raw_records")
    op.drop_table("scanner_raw_records")
