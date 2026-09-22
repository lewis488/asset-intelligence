"""Replace is_admin boolean with three-tier role system

Revision ID: 015_role_three_tier
Revises: 014_users_is_admin
Create Date: 2026-09-22

Migrates the dual-column permission model (role string + is_admin boolean)
to a single role column with values: admin, manager, viewer.

is_admin=true  -> role='admin'
is_admin=false -> role='manager' (unless already 'viewer')
New default: 'manager'
"""
import sqlalchemy as sa
from alembic import op

revision = "015_role_three_tier"
down_revision = "014_users_is_admin"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE users SET role = 'admin'   WHERE is_admin = true"))
    conn.execute(sa.text("UPDATE users SET role = 'manager' WHERE is_admin = false AND role != 'viewer'"))
    op.drop_column("users", "is_admin")
    op.alter_column("users", "role", server_default="manager")


def downgrade():
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), server_default="false", nullable=False),
    )
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE users SET is_admin = true WHERE role = 'admin'"))
    conn.execute(sa.text("UPDATE users SET role = 'analyst' WHERE role = 'manager'"))
    op.alter_column("users", "role", server_default="analyst")
