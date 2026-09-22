"""Add authority_id to secondary survey tables; add slug to authorities

Revision ID: 012_authority_id_survey_tables
Revises: 011_us_pavement_schema
Create Date: 2026-09-21

Phase 1 — columns only, nullable. No backfill. Phase 2 backfills,
Phase 3 enforces NOT NULL and updates upload stamping.

Tables already carrying direct authority_id (no change):
  authorities, users, assets, network_assets, vaisala_surveys

Tables receiving new authority_id FK (nullable):
  scanner_raw_records, cvi_raw_records, scrim_records,
  reactive_job_records, reactive_aggregates,
  vaisala_sections, vaisala_intervals
"""
import sqlalchemy as sa
from alembic import op

revision = "012_authority_id_survey_tables"
down_revision = "011_us_pavement_schema"
branch_labels = None
depends_on = None

_TABLES = [
    "scanner_raw_records",
    "cvi_raw_records",
    "scrim_records",
    "reactive_job_records",
    "reactive_aggregates",
    "vaisala_sections",
    "vaisala_intervals",
]


def upgrade():
    # ── authorities: add slug for human-readable authority keys ──────────────
    op.add_column("authorities", sa.Column("slug", sa.String(), nullable=True))
    op.create_index("ix_authorities_slug", "authorities", ["slug"], unique=True)

    # ── secondary survey tables: add nullable authority_id FK + index ────────
    for table in _TABLES:
        op.add_column(table, sa.Column("authority_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_authority_id",
            table, "authorities",
            ["authority_id"], ["id"],
        )
        op.create_index(f"ix_{table}_authority_id", table, ["authority_id"])


def downgrade():
    for table in reversed(_TABLES):
        op.drop_index(f"ix_{table}_authority_id", table_name=table)
        op.drop_constraint(f"fk_{table}_authority_id", table, type_="foreignkey")
        op.drop_column(table, "authority_id")

    op.drop_index("ix_authorities_slug", table_name="authorities")
    op.drop_column("authorities", "slug")
