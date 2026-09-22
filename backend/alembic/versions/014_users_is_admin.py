"""Add is_admin boolean to users; set true for existing users

Revision ID: 014_users_is_admin
Revises: 013_backfill_admin_authority
Create Date: 2026-09-21

is_admin is a role flag on a User — completely separate from
which authority_id that user belongs to. A user can have
is_admin=true while belonging to any authority.

All existing users are set to is_admin=true because they are
Admin-authority operators. New users created via POST /auth/register
default to is_admin=false.
"""
import sqlalchemy as sa
from alembic import op

revision = "014_users_is_admin"
down_revision = "013_backfill_admin_authority"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), server_default="false", nullable=False),
    )
    # Existing users are Admin-authority operators
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE users SET is_admin = true"))


def downgrade():
    op.drop_column("users", "is_admin")
