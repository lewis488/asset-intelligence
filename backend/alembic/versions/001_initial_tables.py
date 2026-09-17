"""Initial tables

Revision ID: 001_initial_tables
Revises:
Create Date: 2026-06-02
"""
import sqlalchemy as sa
from alembic import op

revision = "001_initial_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "authorities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("region", sa.String()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("authority_id", sa.Integer(), sa.ForeignKey("authorities.id"), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="analyst"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("authority_id", sa.Integer(), sa.ForeignKey("authorities.id"), nullable=False),
        sa.Column("nsg_ref", sa.String(), nullable=False),
        sa.Column("road_name", sa.String()),
        sa.Column("parish", sa.String()),
        sa.Column("road_class", sa.String()),
        sa.Column("length_m", sa.Float()),
        sa.Column("geometry", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_assets_nsg_ref", "assets", ["nsg_ref"])

    op.create_table(
        "scanner_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("survey_year", sa.Integer()),
        sa.Column("avg_ci", sa.Float()),
        sa.Column("rci_band", sa.String()),
        sa.Column("defect_overall_pct", sa.Float()),
        sa.Column("defect_rutting_pct", sa.Float()),
        sa.Column("defect_cracking_pct", sa.Float()),
        sa.Column("defect_texture_pct", sa.Float()),
        sa.Column("defect_lpv_pct", sa.Float()),
        sa.Column("amber_length_m", sa.Float()),
        sa.Column("amber_pct", sa.Float()),
        sa.Column("amber_rutting", sa.Float()),
        sa.Column("amber_cracking", sa.Float()),
        sa.Column("amber_texture", sa.Float()),
        sa.Column("amber_lpv", sa.Float()),
        sa.Column("red_length_m", sa.Float()),
        sa.Column("red_pct", sa.Float()),
        sa.Column("red_rutting", sa.Float()),
        sa.Column("red_cracking", sa.Float()),
        sa.Column("red_texture", sa.Float()),
        sa.Column("red_lpv", sa.Float()),
        sa.Column("ci_contribution_rutting", sa.Float()),
        sa.Column("ci_contribution_cracking", sa.Float()),
        sa.Column("ci_contribution_texture", sa.Float()),
        sa.Column("ci_contribution_lpv", sa.Float()),
        sa.Column("edi_avg", sa.Float()),
        sa.Column("source_file", sa.String()),
        sa.Column("ingested_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "cvi_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("survey_year", sa.Integer()),
        sa.Column("structural_ci", sa.Float()),
        sa.Column("edge_ci", sa.Float()),
        sa.Column("wearing_course_ci", sa.Float()),
        sa.Column("structural_flagged", sa.Boolean(), server_default="false"),
        sa.Column("edge_flagged", sa.Boolean(), server_default="false"),
        sa.Column("wearing_course_flagged", sa.Boolean(), server_default="false"),
        sa.Column("source_file", sa.String()),
        sa.Column("ingested_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "reactive_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("nsg_ref", sa.String()),
        sa.Column("job_ref", sa.String()),
        sa.Column("job_type", sa.String()),
        sa.Column("defect_type", sa.String()),
        sa.Column("job_date", sa.DateTime()),
        sa.Column("cost_gbp", sa.Float()),
        sa.Column("response_category", sa.String()),
        sa.Column("source_file", sa.String()),
        sa.Column("ingested_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_reactive_jobs_nsg_ref", "reactive_jobs", ["nsg_ref"])

    op.create_table(
        "risk_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("scored_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("composite_score", sa.Float()),
        sa.Column("risk_band", sa.String()),
        sa.Column("ci_score", sa.Float()),
        sa.Column("defect_driver_score", sa.Float()),
        sa.Column("reactive_score", sa.Float()),
        sa.Column("edi_score", sa.Float()),
        sa.Column("dominant_defect_driver", sa.String()),
        sa.Column("treatment_recommendation", sa.Text()),
        sa.Column("scoring_version", sa.String()),
    )

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("authority_id", sa.Integer(), sa.ForeignKey("authorities.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("priority_list_json", sa.JSON()),
        sa.Column("parameters_used", sa.JSON()),
    )


def downgrade():
    op.drop_table("analysis_runs")
    op.drop_table("risk_scores")
    op.drop_index("ix_reactive_jobs_nsg_ref", "reactive_jobs")
    op.drop_table("reactive_jobs")
    op.drop_table("cvi_records")
    op.drop_table("scanner_records")
    op.drop_index("ix_assets_nsg_ref", "assets")
    op.drop_table("assets")
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
    op.drop_table("authorities")
