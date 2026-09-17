"""Add vaisala_network_geometries + vaisala_network_features for Map tab basemap join

Revision ID: 010_vaisala_network_geometry
Revises: 009_vaisala_intervals_extras
Create Date: 2026-09-14
"""
import sqlalchemy as sa
from alembic import op

revision = "010_vaisala_network_geometry"
down_revision = "009_vaisala_intervals_extras"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vaisala_network_geometries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("authority_id", sa.Integer(), sa.ForeignKey("authorities.id"), nullable=False),
        sa.Column("source_filename", sa.String(), nullable=False),
        sa.Column("section_field", sa.String(), nullable=False),
        sa.Column("feature_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("crs_wkt", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_vaisala_network_geom_authority", "vaisala_network_geometries", ["authority_id"])

    op.create_table(
        "vaisala_network_features",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("geometry_id", sa.Integer(), sa.ForeignKey("vaisala_network_geometries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_key", sa.String(), nullable=False),
        sa.Column("geometry_geojson", sa.Text(), nullable=False),
    )
    op.create_index("ix_vaisala_network_features_geometry", "vaisala_network_features", ["geometry_id"])
    op.create_index("ix_vaisala_network_features_key", "vaisala_network_features", ["geometry_id", "section_key"])


def downgrade():
    op.drop_index("ix_vaisala_network_features_key", "vaisala_network_features")
    op.drop_index("ix_vaisala_network_features_geometry", "vaisala_network_features")
    op.drop_table("vaisala_network_features")
    op.drop_index("ix_vaisala_network_geom_authority", "vaisala_network_geometries")
    op.drop_table("vaisala_network_geometries")
