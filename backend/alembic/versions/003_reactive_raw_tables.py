"""Add reactive_job_records and reactive_aggregates tables

Revision ID: 003_reactive_raw_tables
Revises: 002_raw_confirm_tables
Create Date: 2026-06-05
"""
import sqlalchemy as sa
from alembic import op

revision = "003_reactive_raw_tables"
down_revision = "002_raw_confirm_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reactive_job_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_number", sa.String(), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("nsg_ref", sa.String()),
        sa.Column("job_entry_date", sa.DateTime()),
        sa.Column("actual_comp_date", sa.DateTime()),
        sa.Column("priority_name", sa.String()),
        sa.Column("priority_category", sa.Integer()),
        sa.Column("job_type_name", sa.String()),
        sa.Column("job_type_category", sa.String()),
        sa.Column("status_name", sa.String()),
        sa.Column("district_name", sa.String()),
        sa.Column("locality_name", sa.String()),
        sa.Column("town_name", sa.String()),
        sa.Column("road_class", sa.String()),
        sa.Column("easting", sa.Float()),
        sa.Column("northing", sa.Float()),
        sa.Column("source_file", sa.String()),
        sa.Column("ingested_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("job_number", name="uq_reactive_job_number"),
    )
    op.create_index("ix_reactive_job_records_nsg_ref", "reactive_job_records", ["nsg_ref"])
    op.create_index("ix_reactive_job_records_job_number", "reactive_job_records", ["job_number"])

    op.create_table(
        "reactive_aggregates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("nsg_ref", sa.String()),
        sa.Column("year", sa.Integer()),
        sa.Column("total_jobs_raised", sa.Integer()),
        sa.Column("emergency_jobs_2hr", sa.Integer()),
        sa.Column("urgent_jobs_24hr", sa.Integer()),
        sa.Column("jobs_5day", sa.Integer()),
        sa.Column("jobs_28day", sa.Integer()),
        sa.Column("pothole_count", sa.Integer()),
        sa.Column("patching_count", sa.Integer()),
        sa.Column("edge_count", sa.Integer()),
        sa.Column("drainage_count", sa.Integer()),
        sa.Column("other_count", sa.Integer()),
        sa.Column("days_since_most_recent_defect", sa.Integer()),
        sa.Column("most_recent_defect_date", sa.DateTime()),
        sa.Column("jobs_completed", sa.Integer()),
        sa.Column("jobs_outstanding", sa.Integer()),
        sa.Column("mean_days_to_completion", sa.Float()),
        sa.Column("oldest_outstanding_days", sa.Integer()),
        sa.Column("rebuilt_at", sa.DateTime()),
        sa.UniqueConstraint("asset_id", "year", name="uq_reactive_agg_asset_year"),
    )
    op.create_index("ix_reactive_aggregates_nsg_ref", "reactive_aggregates", ["nsg_ref"])


def downgrade():
    op.drop_index("ix_reactive_aggregates_nsg_ref", "reactive_aggregates")
    op.drop_table("reactive_aggregates")
    op.drop_index("ix_reactive_job_records_job_number", "reactive_job_records")
    op.drop_index("ix_reactive_job_records_nsg_ref", "reactive_job_records")
    op.drop_table("reactive_job_records")
