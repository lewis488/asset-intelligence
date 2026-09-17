from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    authority_id = Column(Integer, ForeignKey("authorities.id"), nullable=False)
    nsg_ref = Column(String, nullable=False, index=True)
    road_name = Column(String)
    parish = Column(String)
    road_class = Column(String)  # A | BC | U
    length_m = Column(Float)
    geometry = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    authority = relationship("Authority", back_populates="assets")
    scanner_records = relationship("ScannerRecord", back_populates="asset", cascade="all, delete-orphan")
    cvi_records = relationship("CviRecord", back_populates="asset", cascade="all, delete-orphan")
    reactive_jobs = relationship("ReactiveJob", back_populates="asset", cascade="all, delete-orphan")
    risk_scores = relationship("RiskScore", back_populates="asset", cascade="all, delete-orphan",
                               order_by="RiskScore.scored_at.desc()")


class ScannerRecord(Base):
    __tablename__ = "scanner_records"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    survey_year = Column(Integer)
    avg_ci = Column(Float)
    rci_band = Column(String)  # Green | Amber | Red

    # ── Defect length percentages (% of section length) ──────────────────────
    defect_overall_pct = Column(Float)
    defect_rutting_pct = Column(Float)
    defect_cracking_pct = Column(Float)
    defect_texture_pct = Column(Float)
    defect_lpv_pct = Column(Float)

    # ── Amber band ────────────────────────────────────────────────────────────
    amber_length_m = Column(Float)
    amber_pct = Column(Float)
    amber_rutting = Column(Float)
    amber_cracking = Column(Float)
    amber_texture = Column(Float)
    amber_lpv = Column(Float)

    # ── Red band ──────────────────────────────────────────────────────────────
    red_length_m = Column(Float)
    red_pct = Column(Float)
    red_rutting = Column(Float)
    red_cracking = Column(Float)
    red_texture = Column(Float)
    red_lpv = Column(Float)

    # ── CI driver contributions (proportional, sum to 1.0) ───────────────────
    ci_contribution_rutting = Column(Float)
    ci_contribution_cracking = Column(Float)
    ci_contribution_texture = Column(Float)
    ci_contribution_lpv = Column(Float)

    # ── EDI (B+C roads only) ──────────────────────────────────────────────────
    edi_avg = Column(Float)

    source_file = Column(String)
    ingested_at = Column(DateTime, server_default=func.now())

    asset = relationship("Asset", back_populates="scanner_records")


class CviRecord(Base):
    __tablename__ = "cvi_records"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    survey_year = Column(Integer)

    structural_ci = Column(Float)
    edge_ci = Column(Float)
    wearing_course_ci = Column(Float)

    # BV224b threshold flags
    structural_flagged = Column(Boolean, default=False)
    edge_flagged = Column(Boolean, default=False)
    wearing_course_flagged = Column(Boolean, default=False)

    source_file = Column(String)
    ingested_at = Column(DateTime, server_default=func.now())

    asset = relationship("Asset", back_populates="cvi_records")


class ReactiveJob(Base):
    __tablename__ = "reactive_jobs"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    nsg_ref = Column(String, index=True)
    job_ref = Column(String)
    job_type = Column(String)
    defect_type = Column(String)
    job_date = Column(DateTime)
    cost_gbp = Column(Float)
    response_category = Column(String)  # Emergency | Urgent | Planned
    source_file = Column(String)
    ingested_at = Column(DateTime, server_default=func.now())

    asset = relationship("Asset", back_populates="reactive_jobs")


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    scored_at = Column(DateTime, server_default=func.now())

    composite_score = Column(Float)
    risk_band = Column(String)
    ci_score = Column(Float)
    defect_driver_score = Column(Float)
    reactive_score = Column(Float)
    edi_score = Column(Float)
    dominant_defect_driver = Column(String)
    treatment_recommendation = Column(Text)
    urgency = Column(String)
    confidence = Column(String)
    scoring_version = Column(String)

    asset = relationship("Asset", back_populates="risk_scores")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, index=True)
    authority_id = Column(Integer, ForeignKey("authorities.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    summary_text = Column(Text, nullable=False)
    priority_list_json = Column(JSON)
    parameters_used = Column(JSON)

    authority = relationship("Authority", back_populates="analysis_runs")


# ── Raw Confirm format models ─────────────────────────────────────────────────

class ScannerRawRecord(Base):
    """One aggregated record per (NSG, survey_year, offset_direction) from Confirm SCANNER export."""
    __tablename__ = "scanner_raw_records"
    __table_args__ = (
        UniqueConstraint("asset_id", "survey_year", "offset_direction",
                         name="uq_scanner_raw_asset_year_dir"),
    )

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    survey_year = Column(Integer)
    survey_date = Column(DateTime)
    survey_number = Column(String)
    total_length_m = Column(Float)
    avg_ci = Column(Float)
    red_pct = Column(Float)
    amber_pct = Column(Float)
    green_pct = Column(Float)
    max_ci = Column(Float)
    min_ci = Column(Float)
    rci_band = Column(String)       # Green | Amber | Red
    offset_direction = Column(String)  # nearside | offside | centre
    source_file = Column(String)
    ingested_at = Column(DateTime, server_default=func.now())


class CviRawRecord(Base):
    """One aggregated record per (NSG, survey_year) from Confirm CVI export."""
    __tablename__ = "cvi_raw_records"
    __table_args__ = (
        UniqueConstraint("asset_id", "survey_year", name="uq_cvi_raw_asset_year"),
    )

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    survey_year = Column(Integer)
    survey_date = Column(DateTime)
    survey_name = Column(String)
    total_length_m = Column(Float)
    avg_ci_overall = Column(Float)          # length-weighted average CI_OVRLL
    max_ci_structural = Column(Float)
    max_ci_edge = Column(Float)
    max_ci_wearingcourse = Column(Float)
    structural_flagged = Column(Boolean, default=False)   # >= 85
    edge_flagged = Column(Boolean, default=False)         # >= 50
    wearingcourse_flagged = Column(Boolean, default=False)  # >= 60
    any_flagged = Column(Boolean, default=False)
    pct_length_structural_flagged = Column(Float)
    pct_length_edge_flagged = Column(Float)
    pct_length_wc_flagged = Column(Float)
    source_file = Column(String)
    ingested_at = Column(DateTime, server_default=func.now())


class ScrimRecord(Base):
    """One aggregated record per (NSG, survey_year) from Confirm SCRIM export."""
    __tablename__ = "scrim_records"
    __table_args__ = (
        UniqueConstraint("asset_id", "survey_year", name="uq_scrim_asset_year"),
    )

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    survey_year = Column(Integer)
    survey_date = Column(DateTime)
    survey_name = Column(String)
    survey_number = Column(String)
    total_sections = Column(Integer)
    dominant_ilct = Column(String)    # most common site category code
    sfct_threshold = Column(Float)    # investigatory level for this NSG
    mean_sfc = Column(Float)          # mean SFC excluding zeros (no-reading rows)
    min_sfc = Column(Float)           # worst (lowest) SFC excluding zeros
    sections_below_il = Column(Integer)
    pct_below_il = Column(Float)
    safety_flagged = Column(Boolean, default=False)  # any section XDIF < 0
    worst_xdif = Column(Float)        # most negative XDIF (largest deficit)
    source_file = Column(String)
    ingested_at = Column(DateTime, server_default=func.now())


# ── Reactive jobs raw tables ──────────────────────────────────────────────────

class ReactiveJobRecord(Base):
    """One row per reactive job from a Confirm export, filtered to condition-relevant types."""
    __tablename__ = "reactive_job_records"
    __table_args__ = (
        UniqueConstraint("job_number", name="uq_reactive_job_number"),
    )

    id = Column(Integer, primary_key=True, index=True)
    job_number = Column(String, nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    nsg_ref = Column(String, index=True)
    job_entry_date = Column(DateTime)
    actual_comp_date = Column(DateTime)
    priority_name = Column(String)
    priority_category = Column(Integer)       # 1–5
    job_type_name = Column(String)
    job_type_category = Column(String)        # pothole | patching | edge | drainage | other
    status_name = Column(String)
    district_name = Column(String)
    locality_name = Column(String)
    town_name = Column(String)
    road_class = Column(String)
    easting = Column(Float)
    northing = Column(Float)
    source_file = Column(String)
    ingested_at = Column(DateTime, server_default=func.now())


class ReactiveAggregate(Base):
    """Per-(asset, year) aggregate rebuilt from ReactiveJobRecord on every upload."""
    __tablename__ = "reactive_aggregates"
    __table_args__ = (
        UniqueConstraint("asset_id", "year", name="uq_reactive_agg_asset_year"),
    )

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    nsg_ref = Column(String, index=True)
    year = Column(Integer)

    # Defect signals (based on job_entry_date)
    total_jobs_raised = Column(Integer)
    emergency_jobs_2hr = Column(Integer)
    urgent_jobs_24hr = Column(Integer)
    jobs_5day = Column(Integer)
    jobs_28day = Column(Integer)
    pothole_count = Column(Integer)
    patching_count = Column(Integer)
    edge_count = Column(Integer)
    drainage_count = Column(Integer)
    other_count = Column(Integer)
    days_since_most_recent_defect = Column(Integer)
    most_recent_defect_date = Column(DateTime)

    # Operational signals (based on actual_comp_date)
    jobs_completed = Column(Integer)
    jobs_outstanding = Column(Integer)
    mean_days_to_completion = Column(Float)
    oldest_outstanding_days = Column(Integer)

    rebuilt_at = Column(DateTime)


# ── Network master register ───────────────────────────────────────────────────

class NetworkAsset(Base):
    """One row per NSG reference — aggregated from the WSCC road network shapefile."""
    __tablename__ = "network_assets"
    __table_args__ = (
        UniqueConstraint("authority_id", "nsg_ref", name="uq_network_asset_auth_nsg"),
    )

    id = Column(Integer, primary_key=True, index=True)
    authority_id = Column(Integer, ForeignKey("authorities.id"), nullable=False)
    nsg_ref = Column(String, nullable=False, index=True)
    wsccnet = Column(String)
    road_name = Column(String)
    road_class = Column(String)
    length_m = Column(Float)
    avg_width_m = Column(Float)
    area_m2 = Column(Float)
    parish = Column(String)
    locality = Column(String)
    district = Column(String)
    urban_rural = Column(String)
    speed_limit = Column(String)
    inspection_freq = Column(String)
    geometry = Column(Text)          # WKT LineString/MultiLineString, EPSG:4326
    source_file = Column(String)
    ingested_at = Column(DateTime, server_default=func.now())
