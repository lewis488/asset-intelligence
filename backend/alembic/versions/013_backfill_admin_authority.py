"""Create Admin authority and backfill authority_id on all tables

Revision ID: 013_backfill_admin_authority
Revises: 012_authority_id_survey_tables
Create Date: 2026-09-21

Creates one holding authority ("Admin", slug "admin") and assigns
every existing row in every table to it. Columns remain nullable
until Phase 3 migration 015 enforces NOT NULL after user confirms counts.

Tables with pre-existing authority_id (updated from old values to Admin):
  assets, vaisala_surveys, network_assets, users

Tables with new nullable authority_id column from 012 (set to Admin):
  scanner_raw_records, cvi_raw_records, scrim_records,
  reactive_job_records, reactive_aggregates,
  vaisala_sections, vaisala_intervals
"""
import sqlalchemy as sa
from alembic import op

revision = "013_backfill_admin_authority"
down_revision = "012_authority_id_survey_tables"
branch_labels = None
depends_on = None

# Tables receiving a NEW authority_id (from migration 012 — previously NULL)
_NEW_AUTHORITY_TABLES = [
    "scanner_raw_records",
    "cvi_raw_records",
    "scrim_records",
    "reactive_job_records",
    "reactive_aggregates",
    "vaisala_sections",
    "vaisala_intervals",
]

# Tables that already had authority_id (may point to old dev authorities)
_EXISTING_AUTHORITY_TABLES = [
    "assets",
    "network_assets",
    "vaisala_surveys",
    "users",
]


def upgrade():
    conn = op.get_bind()

    # Create Admin authority — fail loudly if slug already claimed
    result = conn.execute(sa.text(
        "INSERT INTO authorities (name, slug, created_at) "
        "VALUES ('Admin', 'admin', NOW()) RETURNING id"
    ))
    admin_id = result.fetchone()[0]

    # Backfill tables that already had authority_id
    for table in _EXISTING_AUTHORITY_TABLES:
        conn.execute(
            sa.text(f"UPDATE {table} SET authority_id = :aid"),
            {"aid": admin_id},
        )

    # Backfill tables that received authority_id in migration 012
    for table in _NEW_AUTHORITY_TABLES:
        conn.execute(
            sa.text(f"UPDATE {table} SET authority_id = :aid"),
            {"aid": admin_id},
        )


def downgrade():
    conn = op.get_bind()

    # Clear all authority_id values set by this migration
    for table in _NEW_AUTHORITY_TABLES + _EXISTING_AUTHORITY_TABLES:
        conn.execute(sa.text(f"UPDATE {table} SET authority_id = NULL"))

    conn.execute(sa.text("DELETE FROM authorities WHERE slug = 'admin'"))
