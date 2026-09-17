"""Add network_assets table — WSCC road network master register

Revision ID: 005_network_assets
Revises: 004_risk_scores_treatment
Create Date: 2026-06-08
"""
import sqlalchemy as sa
from alembic import op

revision = "005_network_assets"
down_revision = "004_risk_scores_treatment"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "network_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("authority_id", sa.Integer(), sa.ForeignKey("authorities.id"), nullable=False),
        sa.Column("nsg_ref", sa.String(), nullable=False, index=True),
        sa.Column("wsccnet", sa.String()),
        sa.Column("road_name", sa.String()),
        sa.Column("road_class", sa.String()),
        sa.Column("length_m", sa.Float()),
        sa.Column("avg_width_m", sa.Float()),
        sa.Column("area_m2", sa.Float()),
        sa.Column("parish", sa.String()),
        sa.Column("locality", sa.String()),
        sa.Column("district", sa.String()),
        sa.Column("urban_rural", sa.String()),
        sa.Column("speed_limit", sa.String()),
        sa.Column("inspection_freq", sa.String()),
        sa.Column("geometry", sa.Text()),           # WKT, WGS84 (EPSG:4326)
        sa.Column("source_file", sa.String()),
        sa.Column("ingested_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("authority_id", "nsg_ref", name="uq_network_asset_auth_nsg"),
    )


def downgrade():
    op.drop_table("network_assets")
