"""Per-authority module access control; null means all modules enabled."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = '021_authority_enabled_modules'
down_revision = '020_vaisala_programme'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('authorities', sa.Column('enabled_modules', JSONB(), nullable=True))


def downgrade():
    op.drop_column('authorities', 'enabled_modules')
