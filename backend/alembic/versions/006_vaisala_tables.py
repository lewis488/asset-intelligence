"""Vaisala DST tables

Revision ID: 006_vaisala_tables
Revises: 005_network_assets
Create Date: 2026-08-17
"""
import sqlalchemy as sa
from alembic import op

revision = "006_vaisala_tables"
down_revision = "005_network_assets"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vaisala_defect_weight_sets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("is_rag_validated", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "vaisala_defect_weights",
        sa.Column("weight_set_id", sa.Integer(), sa.ForeignKey("vaisala_defect_weight_sets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("defect_key", sa.String(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.PrimaryKeyConstraint("weight_set_id", "defect_key"),
    )

    op.create_table(
        "vaisala_rag_threshold_sets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("weight_set_id", sa.Integer(), sa.ForeignKey("vaisala_defect_weight_sets.id"), nullable=False),
        sa.Column("red_threshold", sa.Float(), nullable=False),
        sa.Column("amber_threshold", sa.Float(), nullable=False),
        sa.Column("derivation_note", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "vaisala_surveys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("authority_id", sa.Integer(), sa.ForeignKey("authorities.id"), nullable=False),
        sa.Column("source_filename", sa.String(), nullable=False),
        sa.Column("source_format", sa.String(), nullable=False),
        sa.Column("network_key", sa.String(), nullable=False),
        sa.Column("weight_set_id", sa.Integer(), sa.ForeignKey("vaisala_defect_weight_sets.id"), nullable=True),
        sa.Column("threshold_set_id", sa.Integer(), sa.ForeignKey("vaisala_rag_threshold_sets.id"), nullable=True),
        sa.Column("imported_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("section_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("has_weight_drift", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("notes", sa.Text()),
    )

    op.create_table(
        "vaisala_sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("survey_id", sa.Integer(), sa.ForeignKey("vaisala_surveys.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_ref", sa.String(), nullable=False),
        sa.Column("road_name", sa.String()),
        sa.Column("net_reference", sa.String()),
        sa.Column("urban_rural", sa.String()),
        sa.Column("road_class", sa.String()),
        sa.Column("length_m", sa.Float(), nullable=False),
        sa.Column("road_surface_condition", sa.Float()),
        sa.Column("road_surface_condition_class", sa.String()),
        sa.Column("asphalt_condition", sa.Float()),
        sa.Column("asphalt_condition_class", sa.String()),
        sa.Column("pas2161_category", sa.String()),
        sa.Column("priority_score", sa.Float()),
        sa.Column("worst_interval_score", sa.Float()),
        sa.Column("rag_band", sa.String()),
        sa.Column("treatment", sa.String()),
        sa.Column("primary_defect", sa.String()),
        sa.Column("primary_defect_contribution", sa.Float()),
        sa.Column("secondary_defect", sa.String()),
        sa.Column("secondary_defect_contribution", sa.Float()),
        sa.Column("structural_pct", sa.Float()),
        sa.Column("localised_pct", sa.Float()),
        sa.Column("dressing_pct", sa.Float()),
        sa.Column("micro_pct", sa.Float()),
        sa.Column("alligator_pct", sa.Float()),
        sa.Column("edge_pct", sa.Float()),
        sa.Column("qc_completeness_pct", sa.Float()),
        sa.Column("qc_completeness_band", sa.String()),
        sa.Column("qc_reliability_pct", sa.Float()),
        sa.Column("qc_reliability_band", sa.String()),
        sa.UniqueConstraint("survey_id", "section_ref", name="uq_vaisala_section_ref"),
    )
    op.create_index("ix_vaisala_sections_survey", "vaisala_sections", ["survey_id"])
    op.create_index("ix_vaisala_sections_rag", "vaisala_sections", ["rag_band"])
    op.create_index("ix_vaisala_sections_score", "vaisala_sections", ["priority_score"])

    op.create_table(
        "vaisala_rag_drift_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("survey_id", sa.Integer(), sa.ForeignKey("vaisala_surveys.id"), nullable=False),
        sa.Column("defect_key", sa.String(), nullable=False),
        sa.Column("validated_weight", sa.Float(), nullable=False),
        sa.Column("actual_weight", sa.Float(), nullable=False),
        sa.Column("logged_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("vaisala_rag_drift_log")
    op.drop_index("ix_vaisala_sections_score", "vaisala_sections")
    op.drop_index("ix_vaisala_sections_rag", "vaisala_sections")
    op.drop_index("ix_vaisala_sections_survey", "vaisala_sections")
    op.drop_table("vaisala_sections")
    op.drop_table("vaisala_surveys")
    op.drop_table("vaisala_rag_threshold_sets")
    op.drop_table("vaisala_defect_weights")
    op.drop_table("vaisala_defect_weight_sets")
