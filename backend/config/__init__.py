import os
from typing import List
from pydantic_settings import BaseSettings

# Resolve .env relative to __file__ so it works from any CWD.
# backend/config/__init__.py -> three levels up = project root (config/ -> backend/ -> root)
_env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")


class Settings(BaseSettings):
    # ── Core ──────────────────────────────────────────────────────────────────
    anthropic_api_key: str
    database_url: str
    jwt_secret: str
    environment: str = "development"

    llm_model: str = "claude-sonnet-4-5"
    allowed_origins_raw: str = "http://localhost:5173,http://localhost:3000"

    # ── SCANNER CI score (max 40 pts) ─────────────────────────────────────────
    ci_green_threshold: float = 40.0    # CI < 40 → Green
    ci_amber_threshold: float = 100.0   # CI 40–99 → Amber; ≥100 → Red
    ci_green_max: float = 10.0          # max points in Green band
    ci_amber_max: float = 25.0          # max points in Amber band
    ci_red_max: float = 40.0            # max points in Red band

    # ── Defect Driver score (max 30 pts) ─────────────────────────────────────
    dd_lpv_threshold: float = 0.40      # LPV >40% → structural roughness
    dd_lpv_points: float = 15.0
    dd_rutting_threshold: float = 0.35  # Rutting >35% → structural deformation
    dd_rutting_points: float = 15.0
    dd_texture_threshold: float = 0.50  # Texture >50% → surface treatment
    dd_texture_points: float = 8.0
    dd_cracking_threshold: float = 0.40 # Cracking >40% → surface/structural
    dd_cracking_points: float = 12.0
    dd_high_red_threshold: float = 0.15 # >15% section in Red → +10
    dd_high_red_points: float = 10.0
    dd_high_amber_threshold: float = 0.40  # >40% section in Amber → +5
    dd_high_amber_points: float = 5.0

    # ── EDI score (max 15 pts, B+C only) ─────────────────────────────────────
    edi_low_threshold: float = 20.0     # EDI < 20 → 0 pts
    edi_mid_threshold: float = 35.0     # EDI 20–35 → 5 pts
    edi_high_threshold: float = 50.0    # EDI 35–50 → 10 pts; >50 → 15 pts
    edi_low_points: float = 5.0
    edi_mid_points: float = 10.0
    edi_high_points: float = 15.0

    # ── Reactive score (max 15 pts) ───────────────────────────────────────────
    reactive_job_points: float = 3.0    # per job in last 12m
    reactive_job_max: float = 9.0
    reactive_emergency_points: float = 2.0  # per emergency in last 6m
    reactive_emergency_max: float = 6.0
    reactive_lookback_months: int = 12
    reactive_emergency_lookback_months: int = 6

    # ── Risk band thresholds ──────────────────────────────────────────────────
    risk_critical: float = 65.0
    risk_high: float = 40.0
    risk_medium: float = 20.0

    # ── Scoring version — bump when weights change ───────────────────────────
    scoring_version: str = "1.0.0"

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins_raw.split(",") if o.strip()]

    model_config = {"env_file": _env_file, "extra": "ignore"}


settings = Settings()
