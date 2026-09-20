"""Add US pavement management tables (5 tables + 7 enum types)

Revision ID: 011_us_pavement_schema
Revises: 010_vaisala_network_geometry
Create Date: 2026-09-20
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "011_us_pavement_schema"
down_revision = "010_vaisala_network_geometry"
branch_labels = None
depends_on = None

# Define enum types once — referenced by multiple tables with create_type=False
_functional_class = postgresql.ENUM(
    'principal_arterial', 'minor_arterial', 'collector', 'local_street',
    name='us_functional_class',
)
_urban_rural = postgresql.ENUM('urban', 'rural', name='us_urban_rural')
_pci_category = postgresql.ENUM(
    'excellent', 'good', 'satisfactory', 'fair', 'poor', 'serious', 'failed',
    name='us_pci_category',
)
_distress_severity = postgresql.ENUM('low', 'medium', 'high', name='us_distress_severity')
_survey_method = postgresql.ENUM('automated', 'manual', 'hybrid', name='us_survey_method')
_measurement_unit = postgresql.ENUM('sq_ft', 'linear_ft', 'count', name='us_measurement_unit')
_treatment_type = postgresql.ENUM(
    'crackseal', 'rejuvenator', 'microsurfacing', 'pressurepave',
    'thin_lift', 'mill_and_overlay', 'fdr', 'reconstruction',
    name='us_treatment_type',
)


def upgrade():
    bind = op.get_bind()

    # Create all enum types first — idempotent via checkfirst
    _functional_class.create(bind, checkfirst=True)
    _urban_rural.create(bind, checkfirst=True)
    _pci_category.create(bind, checkfirst=True)
    _distress_severity.create(bind, checkfirst=True)
    _survey_method.create(bind, checkfirst=True)
    _measurement_unit.create(bind, checkfirst=True)
    _treatment_type.create(bind, checkfirst=True)

    # Table 1: us_pavement_sections — master asset register
    op.create_table(
        "us_pavement_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("authority_id", sa.Integer(), sa.ForeignKey("authorities.id"), nullable=False),
        sa.Column("section_ref", sa.String(), nullable=False),
        sa.Column("road_name", sa.String()),
        sa.Column("functional_class",
                  postgresql.ENUM('principal_arterial', 'minor_arterial', 'collector', 'local_street',
                                  name='us_functional_class', create_type=False),
                  nullable=False),
        sa.Column("length_ft", sa.Float()),
        sa.Column("width_ft", sa.Float()),
        sa.Column("area_sy", sa.Float()),
        sa.Column("urban_rural",
                  postgresql.ENUM('urban', 'rural', name='us_urban_rural', create_type=False)),
        sa.Column("geometry", sa.Text()),
        sa.Column("source_file", sa.String()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("authority_id", "section_ref", name="uq_us_section_auth_ref"),
    )
    op.create_index("ix_us_pavement_sections_authority_id", "us_pavement_sections", ["authority_id"])
    op.create_index("ix_us_pavement_sections_section_ref", "us_pavement_sections", ["section_ref"])

    # Table 2: us_pci_records — PCI survey results per section per date
    op.create_table(
        "us_pci_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("authority_id", sa.Integer(), sa.ForeignKey("authorities.id"), nullable=False),
        sa.Column("section_ref", sa.String(), nullable=False),
        sa.Column("survey_date", sa.Date(), nullable=False),
        sa.Column("survey_year", sa.Integer(), nullable=False),
        sa.Column("pci_score", sa.Float(), nullable=False),
        sa.Column("condition_category",
                  postgresql.ENUM('excellent', 'good', 'satisfactory', 'fair', 'poor', 'serious', 'failed',
                                  name='us_pci_category', create_type=False),
                  nullable=False),
        sa.Column("dominant_distress_type", sa.String()),
        sa.Column("dominant_distress_severity",
                  postgresql.ENUM('low', 'medium', 'high',
                                  name='us_distress_severity', create_type=False)),
        sa.Column("total_deduct_value", sa.Float()),
        sa.Column("max_cdv", sa.Float()),
        sa.Column("sample_coverage_pct", sa.Float()),
        sa.Column("survey_method",
                  postgresql.ENUM('automated', 'manual', 'hybrid',
                                  name='us_survey_method', create_type=False),
                  nullable=False),
        sa.Column("source_file", sa.String()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("authority_id", "section_ref", "survey_date",
                            name="uq_us_pci_auth_ref_date"),
    )
    op.create_index("ix_us_pci_records_authority_id", "us_pci_records", ["authority_id"])
    op.create_index("ix_us_pci_records_section_ref", "us_pci_records", ["section_ref"])

    # Table 3: us_distress_details — per-distress ASTM D6433 rows
    op.create_table(
        "us_distress_details",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("authority_id", sa.Integer(), sa.ForeignKey("authorities.id"), nullable=False),
        sa.Column("section_ref", sa.String(), nullable=False),
        sa.Column("survey_date", sa.Date(), nullable=False),
        sa.Column("distress_code", sa.String(), nullable=False),
        sa.Column("distress_name", sa.String(), nullable=False),
        sa.Column("severity",
                  postgresql.ENUM('low', 'medium', 'high',
                                  name='us_distress_severity', create_type=False),
                  nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("measurement_unit",
                  postgresql.ENUM('sq_ft', 'linear_ft', 'count',
                                  name='us_measurement_unit', create_type=False),
                  nullable=False),
        sa.Column("density_pct", sa.Float()),
        sa.Column("deduct_value", sa.Float()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_us_distress_details_authority_id", "us_distress_details", ["authority_id"])
    op.create_index("ix_us_distress_details_section_ref", "us_distress_details", ["section_ref"])

    # Table 4: us_treatment_rates — authority-configurable USD/SY cost rates
    op.create_table(
        "us_treatment_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("authority_id", sa.Integer(), sa.ForeignKey("authorities.id"), nullable=False),
        sa.Column("treatment_type",
                  postgresql.ENUM('crackseal', 'rejuvenator', 'microsurfacing', 'pressurepave',
                                  'thin_lift', 'mill_and_overlay', 'fdr', 'reconstruction',
                                  name='us_treatment_type', create_type=False),
                  nullable=False),
        sa.Column("treatment_name", sa.String(), nullable=False),
        sa.Column("cost_per_sy", sa.Float(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("authority_id", "treatment_type", "effective_from",
                            name="uq_us_treatment_auth_type_date"),
    )
    op.create_index("ix_us_treatment_rates_authority_id", "us_treatment_rates", ["authority_id"])

    # Table 5: us_composite_scores — priority scores rebuilt per score run
    op.create_table(
        "us_composite_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("authority_id", sa.Integer(), sa.ForeignKey("authorities.id"), nullable=False),
        sa.Column("section_ref", sa.String(), nullable=False),
        sa.Column("scored_at", sa.DateTime(), nullable=False),
        sa.Column("pci_score", sa.Float()),
        sa.Column("pci_band", sa.String()),
        sa.Column("survey_year", sa.Integer()),
        sa.Column("deterioration_rate", sa.Float()),
        sa.Column("years_to_threshold", sa.Float()),
        sa.Column("recommended_treatment", sa.String()),
        sa.Column("treatment_cost_total", sa.Float()),
        sa.Column("priority_score", sa.Float()),
        sa.Column("priority_rank", sa.Integer()),
        sa.Column("score_components", sa.JSON()),
        sa.Column("datasets_used", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("authority_id", "section_ref", "scored_at",
                            name="uq_us_score_auth_ref_time"),
    )
    op.create_index("ix_us_composite_scores_authority_id", "us_composite_scores", ["authority_id"])
    op.create_index("ix_us_composite_scores_section_ref", "us_composite_scores", ["section_ref"])


def downgrade():
    op.drop_table("us_composite_scores")
    op.drop_table("us_treatment_rates")
    op.drop_table("us_distress_details")
    op.drop_table("us_pci_records")
    op.drop_table("us_pavement_sections")

    bind = op.get_bind()
    _treatment_type.drop(bind, checkfirst=True)
    _measurement_unit.drop(bind, checkfirst=True)
    _survey_method.drop(bind, checkfirst=True)
    _distress_severity.drop(bind, checkfirst=True)
    _pci_category.drop(bind, checkfirst=True)
    _urban_rural.drop(bind, checkfirst=True)
    _functional_class.drop(bind, checkfirst=True)
