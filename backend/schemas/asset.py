from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel


class ScannerDataOut(BaseModel):
    avg_ci: Optional[float] = None
    rci_band: Optional[str] = None
    survey_year: Optional[int] = None
    red_pct: Optional[float] = None
    amber_pct: Optional[float] = None
    model_config = {"from_attributes": True}


class CviDataOut(BaseModel):
    max_ci_structural: Optional[float] = None
    max_ci_edge: Optional[float] = None
    max_ci_wearingcourse: Optional[float] = None
    structural_flagged: Optional[bool] = None
    edge_flagged: Optional[bool] = None
    wearingcourse_flagged: Optional[bool] = None
    any_flagged: Optional[bool] = None
    survey_year: Optional[int] = None
    model_config = {"from_attributes": True}


class ScrimDataOut(BaseModel):
    safety_flagged: Optional[bool] = None
    pct_below_il: Optional[float] = None
    worst_xdif: Optional[float] = None
    mean_sfc: Optional[float] = None
    sfct_threshold: Optional[float] = None
    survey_year: Optional[int] = None
    model_config = {"from_attributes": True}


class ReactiveDataOut(BaseModel):
    total_jobs_raised: Optional[int] = None
    emergency_jobs_2hr: Optional[int] = None
    urgent_jobs_24hr: Optional[int] = None
    pothole_count: Optional[int] = None
    edge_count: Optional[int] = None
    mean_days_to_completion: Optional[float] = None
    days_since_most_recent_defect: Optional[int] = None
    year: Optional[int] = None
    model_config = {"from_attributes": True}


class AssetWithScore(BaseModel):
    id: int
    nsg_ref: str
    road_name: Optional[str] = None
    parish: Optional[str] = None
    road_class: Optional[str] = None
    length_m: Optional[float] = None
    composite_score: float
    risk_band: str
    scanner_score: float = 0.0
    cvi_score: float = 0.0
    scrim_score: float = 0.0
    reactive_score: float = 0.0
    has_scanner: bool = False
    has_cvi: bool = False
    has_scrim: bool = False
    has_reactive: bool = False
    score_completeness: int = 0
    dominant_dataset: Optional[str] = None
    survey_year: Optional[int] = None
    treatment_recommendation: Optional[str] = None
    urgency: Optional[str] = None
    cost_low_per_m2: int = 0
    cost_high_per_m2: int = 0
    confidence: Optional[str] = None
    scanner_data: Optional[ScannerDataOut] = None
    cvi_data: Optional[CviDataOut] = None
    scrim_data: Optional[ScrimDataOut] = None
    reactive_data: Optional[ReactiveDataOut] = None
    model_config = {"from_attributes": True}


class PaginatedAssets(BaseModel):
    total: int
    assets: List[AssetWithScore]


class IngestionResult(BaseModel):
    ingested_rows: int
    total_rows: int
    mapped_columns: List[str]
    unmapped_columns: List[str]
    sheets_processed: Optional[List[str]] = None


class AnalysisRunOut(BaseModel):
    id: int
    authority_id: int
    created_at: datetime
    summary_text: str
    priority_list_json: Optional[Any] = None
    parameters_used: Optional[Any] = None
    model_config = {"from_attributes": True}


class QueryRequest(BaseModel):
    question: str
    conversation_history: Optional[List[dict]] = None


class QueryResponse(BaseModel):
    question: str
    answer: str


class RawIngestionResult(BaseModel):
    records_ingested: int
    assets_created: int
    assets_updated: int
    survey_years: List[int]
    unmapped_columns: List[str]
    validation: Optional[Any] = None


class ReactiveRawIngestionResult(BaseModel):
    jobs_ingested: int
    jobs_skipped: int
    jobs_filtered_out: int
    assets_created: int
    aggregates_rebuilt: int
    years_found: List[int]
    job_type_breakdown: dict
    validation: Optional[Any] = None


class NetworkIngestionResult(BaseModel):
    nsgs_ingested: int
    total_length_km: float
    by_class: dict
    coverage_analysis: dict
    validation: Optional[Any] = None
