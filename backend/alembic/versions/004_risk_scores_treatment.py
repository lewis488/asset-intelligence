"""Add urgency and confidence columns to risk_scores

Revision ID: 004_risk_scores_treatment
Revises: 003_reactive_raw_tables
Create Date: 2026-06-07
"""
import sqlalchemy as sa
from alembic import op

revision = "004_risk_scores_treatment"
down_revision = "003_reactive_raw_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("risk_scores", sa.Column("urgency", sa.String()))
    op.add_column("risk_scores", sa.Column("confidence", sa.String()))


def downgrade():
    op.drop_column("risk_scores", "confidence")
    op.drop_column("risk_scores", "urgency")
