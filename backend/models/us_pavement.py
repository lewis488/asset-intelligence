import enum
import uuid
from datetime import date as date_type

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from database import Base

# NOTE: alembic/env.py must include `import models.us_pavement` for future
# autogenerate migrations to detect these models. Not modified here per task scope.


# ── Enum definitions ──────────────────────────────────────────────────────────

class UsFunctionalClass(str, enum.Enum):
    principal_arterial = "principal_arterial"
    minor_arterial = "minor_arterial"
    collector = "collector"
    local_street = "local_street"


class UsUrbanRural(str, enum.Enum):
    urban = "urban"
    rural = "rural"


class UsPciCategory(str, enum.Enum):
    excellent = "excellent"
    good = "good"
    satisfactory = "satisfactory"
    fair = "fair"
    poor = "poor"
    serious = "serious"
    failed = "failed"


class UsDistressSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class UsSurveyMethod(str, enum.Enum):
    automated = "automated"
    manual = "manual"
    hybrid = "hybrid"


class UsMeasurementUnit(str, enum.Enum):
    sq_ft = "sq_ft"
    linear_ft = "linear_ft"
    count = "count"


class UsTreatmentType(str, enum.Enum):
    crackseal = "crackseal"
    rejuvenator = "rejuvenator"
    microsurfacing = "microsurfacing"
    pressurepave = "pressurepave"
    thin_lift = "thin_lift"
    mill_and_overlay = "mill_and_overlay"
    fdr = "fdr"
    reconstruction = "reconstruction"


# ── Models ────────────────────────────────────────────────────────────────────

class UsPavementSection(Base):
    """Master asset register — one row per road section (US equivalent of NetworkAsset/NSG)."""
    __tablename__ = "us_pavement_sections"
    __table_args__ = (
        UniqueConstraint("authority_id", "section_ref", name="uq_us_section_auth_ref"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # authority_id is Integer FK — authorities.id uses Integer PK (not UUID)
    authority_id = Column(Integer, ForeignKey("authorities.id"), nullable=False, index=True)
    section_ref = Column(String, nullable=False, index=True)
    road_name = Column(String)
    functional_class = Column(
        SAEnum(UsFunctionalClass, name="us_functional_class", create_type=False),
        nullable=False,
    )
    length_ft = Column(Float)
    width_ft = Column(Float)
    area_sy = Column(Float)  # length_ft * width_ft / 9 — calculated on ingest
    urban_rural = Column(SAEnum(UsUrbanRural, name="us_urban_rural", create_type=False))
    geometry = Column(Text)  # WKT LineString/MultiLineString EPSG:4326, nullable until SHP upload
    source_file = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class UsPciRecord(Base):
    """One PCI survey record per section per survey date. PCI: 0–100, higher = better."""
    __tablename__ = "us_pci_records"
    __table_args__ = (
        UniqueConstraint("authority_id", "section_ref", "survey_date",
                         name="uq_us_pci_auth_ref_date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    authority_id = Column(Integer, ForeignKey("authorities.id"), nullable=False, index=True)
    section_ref = Column(String, nullable=False, index=True)
    survey_date = Column(Date, nullable=False)
    survey_year = Column(Integer, nullable=False)
    pci_score = Column(Float, nullable=False)
    condition_category = Column(
        SAEnum(UsPciCategory, name="us_pci_category", create_type=False),
        nullable=False,
    )
    dominant_distress_type = Column(String)
    dominant_distress_severity = Column(
        SAEnum(UsDistressSeverity, name="us_distress_severity", create_type=False),
    )
    total_deduct_value = Column(Float)
    max_cdv = Column(Float)
    sample_coverage_pct = Column(Float)
    survey_method = Column(
        SAEnum(UsSurveyMethod, name="us_survey_method", create_type=False),
        nullable=False,
    )
    source_file = Column(String)
    created_at = Column(DateTime, server_default=func.now())


class UsDistressDetail(Base):
    """Per-distress rows per section per survey — supports ASTM D6433 defect driver decomposition."""
    __tablename__ = "us_distress_details"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    authority_id = Column(Integer, ForeignKey("authorities.id"), nullable=False, index=True)
    section_ref = Column(String, nullable=False, index=True)
    survey_date = Column(Date, nullable=False)
    distress_code = Column(String, nullable=False)   # ASTM D6433 code e.g. 'AC-01'
    distress_name = Column(String, nullable=False)   # e.g. 'Alligator Cracking'
    severity = Column(
        SAEnum(UsDistressSeverity, name="us_distress_severity", create_type=False),
        nullable=False,
    )
    quantity = Column(Float, nullable=False)
    measurement_unit = Column(
        SAEnum(UsMeasurementUnit, name="us_measurement_unit", create_type=False),
        nullable=False,
    )
    density_pct = Column(Float)
    deduct_value = Column(Float)
    created_at = Column(DateTime, server_default=func.now())


class UsTreatmentRate(Base):
    """Authority-configurable treatment cost rates in USD/SY."""
    __tablename__ = "us_treatment_rates"
    __table_args__ = (
        UniqueConstraint("authority_id", "treatment_type", "effective_from",
                         name="uq_us_treatment_auth_type_date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    authority_id = Column(Integer, ForeignKey("authorities.id"), nullable=False, index=True)
    treatment_type = Column(
        SAEnum(UsTreatmentType, name="us_treatment_type", create_type=False),
        nullable=False,
    )
    treatment_name = Column(String, nullable=False)
    cost_per_sy = Column(Float, nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)  # null = currently active
    created_at = Column(DateTime, server_default=func.now())


class UsCompositeScore(Base):
    """Calculated priority score per section — rebuilt after each upload or score run."""
    __tablename__ = "us_composite_scores"
    __table_args__ = (
        UniqueConstraint("authority_id", "section_ref", "scored_at",
                         name="uq_us_score_auth_ref_time"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    authority_id = Column(Integer, ForeignKey("authorities.id"), nullable=False, index=True)
    section_ref = Column(String, nullable=False, index=True)
    scored_at = Column(DateTime, nullable=False)
    pci_score = Column(Float)
    pci_band = Column(String)
    survey_year = Column(Integer)
    deterioration_rate = Column(Float)      # PCI points/year — requires 2+ surveys
    years_to_threshold = Column(Float)      # estimated years until PCI < 40
    recommended_treatment = Column(String)
    treatment_cost_total = Column(Float)    # recommended treatment cost * area_sy
    priority_score = Column(Float)
    priority_rank = Column(Integer)         # 1 = highest priority within authority
    score_components = Column(JSON)
    datasets_used = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())


# ── Seed data ─────────────────────────────────────────────────────────────────

# Default rates from Chattanooga Appendix C
_DEFAULT_RATES = [
    (UsTreatmentType.crackseal,       "Crack Seal",                   2.50),
    (UsTreatmentType.rejuvenator,     "Rejuvenator",                  1.50),
    (UsTreatmentType.microsurfacing,  "Microsurfacing",               5.00),
    (UsTreatmentType.pressurepave,    "PressuPave",                  13.00),
    (UsTreatmentType.thin_lift,       "Thin Lift AC Overlay",        14.00),
    (UsTreatmentType.mill_and_overlay,"Mill and Overlay",            18.00),
    (UsTreatmentType.fdr,             "Full Depth Reclamation (FDR)",67.00),
    (UsTreatmentType.reconstruction,  "Reconstruction",             125.00),
]


def seed_default_treatment_rates(db, authority_id: int, effective_from: date_type | None = None) -> None:
    """Insert 8 default treatment rates for authority_id. Call when provisioning a new US authority."""
    from datetime import date
    if effective_from is None:
        effective_from = date.today()
    for treatment_type, treatment_name, cost_per_sy in _DEFAULT_RATES:
        db.add(UsTreatmentRate(
            authority_id=authority_id,
            treatment_type=treatment_type,
            treatment_name=treatment_name,
            cost_per_sy=cost_per_sy,
            effective_from=effective_from,
        ))
    db.commit()
