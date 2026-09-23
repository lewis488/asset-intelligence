"""Retain whether raw defect readings were complete and valid; older rows stay unknown."""
import sqlalchemy as sa
from alembic import op

revision = '019_vaisala_defect_evidence'
down_revision = '018_vaisala_severity_tier_pcts'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('vaisala_sections', 'vaisala_intervals'):
        op.add_column(table, sa.Column('defect_evidence_complete', sa.Boolean(), nullable=True))


def downgrade():
    for table in ('vaisala_intervals', 'vaisala_sections'):
        op.drop_column(table, 'defect_evidence_complete')
