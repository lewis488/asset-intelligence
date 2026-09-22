"""Add active status; existing accounts remain active."""
import sqlalchemy as sa
from alembic import op

revision = "016_users_is_active"
down_revision = "015_role_three_tier"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade():
    op.drop_column("users", "is_active")
