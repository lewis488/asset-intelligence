"""Add extras_json to vaisala_intervals for recovered hyperlinks and pass-through source columns

Revision ID: 009_vaisala_intervals_extras
Revises: 008_vaisala_intervals
Create Date: 2026-09-14
"""
import sqlalchemy as sa
from alembic import op

revision = "009_vaisala_intervals_extras"
down_revision = "008_vaisala_intervals"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("vaisala_intervals", sa.Column("extras_json", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("vaisala_intervals", "extras_json")
