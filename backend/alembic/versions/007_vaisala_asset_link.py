"""Add asset_id FK to vaisala_sections for composite scoring

Links each Vaisala section to an Asset row (via NSGNO → nsg_ref match for WSCC
imports). NULL for Stroud sections where no NSG reference is available.

Revision ID: 007_vaisala_asset_link
Revises: 006_vaisala_tables
Create Date: 2026-08-17
"""
import sqlalchemy as sa
from alembic import op

revision = "007_vaisala_asset_link"
down_revision = "006_vaisala_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "vaisala_sections",
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_vaisala_sections_asset", "vaisala_sections", ["asset_id"])


def downgrade():
    op.drop_index("ix_vaisala_sections_asset", "vaisala_sections")
    op.drop_column("vaisala_sections", "asset_id")
