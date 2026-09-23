from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class VaisalaSectionOut(BaseModel):
    id: int
    survey_id: int
    section_ref: str
    road_name: Optional[str]
    net_reference: Optional[str]
    urban_rural: Optional[str]
    road_class: Optional[str]
    length_m: float
    priority_score: Optional[float]
    worst_interval_score: Optional[float]
    rag_band: Optional[str]
    treatment: Optional[str]
    primary_defect: Optional[str]
    primary_defect_contribution: Optional[float]
    secondary_defect: Optional[str]
    secondary_defect_contribution: Optional[float]
    structural_pct: Optional[float]
    localised_pct: Optional[float]
    dressing_pct: Optional[float]
    micro_pct: Optional[float]
    alligator_pct: Optional[float]
    edge_pct: Optional[float]
    road_surface_condition: Optional[float]
    road_surface_condition_class: Optional[str]
    asphalt_condition: Optional[float]
    asphalt_condition_class: Optional[str]
    pas2161_category: Optional[str]
    qc_completeness_pct: Optional[float]
    qc_completeness_band: Optional[str]
    qc_reliability_pct: Optional[float]
    qc_reliability_band: Optional[str]
    defect_proportions: Optional[dict] = None
    chunk_label: Optional[str] = None

    model_config = {"from_attributes": True}


class VaisalaSurveyOut(BaseModel):
    id: int
    source_filename: str
    source_format: str
    network_key: str
    imported_at: datetime
    row_count: int
    section_count: int
    has_weight_drift: bool
    notes: Optional[str]

    model_config = {"from_attributes": True}


class VaisalaUploadResult(BaseModel):
    survey_id: int
    source_filename: str
    network_key: str
    row_count: int
    section_count: int
    has_weight_drift: bool
    drift_details: List[dict]
    rag_summary: dict
    dup_groups_resolved: int = 0
    info_meta: dict = {}
    flattened_link_warnings: List[str] = []


class VaisalaStats(BaseModel):
    survey_id: int
    source_filename: str
    network_key: str
    imported_at: datetime
    section_count: int
    total_length_km: float
    rag_counts: dict
    rag_length_km: dict
    has_weight_drift: bool
    top_treatments: dict
    has_urban_rural: bool = False


class PaginatedVaisalaSections(BaseModel):
    sections: List[VaisalaSectionOut]
    total: int
    survey_id: int
