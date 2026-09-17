from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base


class VaisalaDefectWeightSet(Base):
    __tablename__ = "vaisala_defect_weight_sets"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String, nullable=False)
    is_rag_validated = Column(Boolean, server_default="false", nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    weights = relationship("VaisalaDefectWeight", back_populates="weight_set", cascade="all, delete-orphan")
    surveys = relationship("VaisalaSurvey", back_populates="weight_set")
    threshold_sets = relationship("VaisalaRagThresholdSet", back_populates="weight_set")


class VaisalaDefectWeight(Base):
    __tablename__ = "vaisala_defect_weights"

    weight_set_id = Column(Integer, ForeignKey("vaisala_defect_weight_sets.id", ondelete="CASCADE"), primary_key=True)
    defect_key = Column(String, primary_key=True)
    weight = Column(Float, nullable=False)
    active = Column(Boolean, server_default="true", nullable=False)

    weight_set = relationship("VaisalaDefectWeightSet", back_populates="weights")


class VaisalaRagThresholdSet(Base):
    __tablename__ = "vaisala_rag_threshold_sets"

    id = Column(Integer, primary_key=True, index=True)
    weight_set_id = Column(Integer, ForeignKey("vaisala_defect_weight_sets.id"), nullable=False)
    red_threshold = Column(Float, nullable=False)
    amber_threshold = Column(Float, nullable=False)
    derivation_note = Column(Text, nullable=False)
    is_active = Column(Boolean, server_default="true", nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    weight_set = relationship("VaisalaDefectWeightSet", back_populates="threshold_sets")
    surveys = relationship("VaisalaSurvey", back_populates="threshold_set")


class VaisalaSurvey(Base):
    __tablename__ = "vaisala_surveys"

    id = Column(Integer, primary_key=True, index=True)
    authority_id = Column(Integer, ForeignKey("authorities.id"), nullable=False)
    source_filename = Column(String, nullable=False)
    source_format = Column(String, nullable=False)
    network_key = Column(String, nullable=False)
    weight_set_id = Column(Integer, ForeignKey("vaisala_defect_weight_sets.id"), nullable=True)
    threshold_set_id = Column(Integer, ForeignKey("vaisala_rag_threshold_sets.id"), nullable=True)
    imported_at = Column(DateTime, server_default=func.now())
    row_count = Column(Integer, nullable=False, default=0)
    section_count = Column(Integer, nullable=False, default=0)
    has_weight_drift = Column(Boolean, server_default="false", nullable=False)
    notes = Column(Text)

    weight_set = relationship("VaisalaDefectWeightSet", back_populates="surveys")
    threshold_set = relationship("VaisalaRagThresholdSet", back_populates="surveys")
    sections = relationship("VaisalaSection", back_populates="survey", cascade="all, delete-orphan")
    intervals = relationship("VaisalaInterval", back_populates="survey", cascade="all, delete-orphan")
    drift_logs = relationship("VaisalaRagDriftLog", back_populates="survey", cascade="all, delete-orphan")


class VaisalaSection(Base):
    __tablename__ = "vaisala_sections"

    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("vaisala_surveys.id", ondelete="CASCADE"), nullable=False)
    section_ref = Column(String, nullable=False)
    road_name = Column(String)
    net_reference = Column(String)
    urban_rural = Column(String)
    road_class = Column(String)
    length_m = Column(Float, nullable=False)
    road_surface_condition = Column(Float)
    road_surface_condition_class = Column(String)
    asphalt_condition = Column(Float)
    asphalt_condition_class = Column(String)
    pas2161_category = Column(String)
    priority_score = Column(Float)
    worst_interval_score = Column(Float)
    rag_band = Column(String)
    treatment = Column(String)
    primary_defect = Column(String)
    primary_defect_contribution = Column(Float)
    secondary_defect = Column(String)
    secondary_defect_contribution = Column(Float)
    structural_pct = Column(Float)
    localised_pct = Column(Float)
    dressing_pct = Column(Float)
    micro_pct = Column(Float)
    alligator_pct = Column(Float)
    edge_pct = Column(Float)
    qc_completeness_pct = Column(Float)
    qc_completeness_band = Column(String)
    qc_reliability_pct = Column(Float)
    qc_reliability_band = Column(String)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)

    # non-column: chunk_label only applies to interval-derived views (10m/100m); DB sections keep None
    chunk_label = None

    __table_args__ = (UniqueConstraint("survey_id", "section_ref", name="uq_vaisala_section_ref"),)

    survey = relationship("VaisalaSurvey", back_populates="sections")
    asset = relationship("Asset", foreign_keys=[asset_id])


class VaisalaInterval(Base):
    """Raw scored interval — one row per Vaisala measurement interval, before section aggregation."""
    __tablename__ = "vaisala_intervals"

    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("vaisala_surveys.id", ondelete="CASCADE"), nullable=False)
    section_ref = Column(String, nullable=False)
    road_name = Column(String)
    net_reference = Column(String)
    urban_rural = Column(String)
    road_class = Column(String)
    from_m = Column(Float)
    to_m = Column(Float)
    length_m = Column(Float, nullable=False)
    interval_score = Column(Float)
    structural = Column(Float)
    localised = Column(Float)
    dressing = Column(Float)
    micro = Column(Float)
    alligator = Column(Float)
    edge = Column(Float)
    primary_defect = Column(String)
    primary_defect_contribution = Column(Float)
    road_surface_condition = Column(Float)
    road_surface_condition_class = Column(String)
    asphalt_condition = Column(Float)
    asphalt_condition_class = Column(String)
    pas2161_category = Column(String)
    time_utc = Column(String)
    extras_json = Column(Text)  # recovered hyperlinks + raw pass-through columns (JSON)

    survey = relationship("VaisalaSurvey", back_populates="intervals")


class VaisalaNetworkGeometry(Base):
    """A client's own network shapefile — provides real road geometry for map basemap join.

    One or more per authority; only one flagged is_active at a time (the current active layer
    used for map rendering). Feature rows keyed by whichever DBF column identifies each section.
    """
    __tablename__ = "vaisala_network_geometries"

    id = Column(Integer, primary_key=True, index=True)
    authority_id = Column(Integer, ForeignKey("authorities.id"), nullable=False)
    source_filename = Column(String, nullable=False)
    section_field = Column(String, nullable=False)
    feature_count = Column(Integer, nullable=False, default=0)
    crs_wkt = Column(Text)
    is_active = Column(Boolean, server_default="true", nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    features = relationship("VaisalaNetworkFeature", back_populates="geometry", cascade="all, delete-orphan")


class VaisalaNetworkFeature(Base):
    __tablename__ = "vaisala_network_features"

    id = Column(Integer, primary_key=True, index=True)
    geometry_id = Column(Integer, ForeignKey("vaisala_network_geometries.id", ondelete="CASCADE"), nullable=False)
    section_key = Column(String, nullable=False)
    geometry_geojson = Column(Text, nullable=False)

    geometry = relationship("VaisalaNetworkGeometry", back_populates="features")


class VaisalaRagDriftLog(Base):
    __tablename__ = "vaisala_rag_drift_log"

    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("vaisala_surveys.id"), nullable=False)
    defect_key = Column(String, nullable=False)
    validated_weight = Column(Float, nullable=False)
    actual_weight = Column(Float, nullable=False)
    logged_at = Column(DateTime, server_default=func.now())

    survey = relationship("VaisalaSurvey", back_populates="drift_logs")
