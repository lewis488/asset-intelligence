"""
Multi-pathway risk scoring engine.

Two pathways:
  - SCANNER (classified A, B, C roads): CI score + defect driver score + EDI score + reactive score
  - CVI (unclassified roads): structural/edge/wearing-course domain scores + reactive score

All weights and thresholds are read from config so they can be tuned without code changes.
Increment scoring_version in config whenever weights change to track model evolution.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from backend.config import settings


@dataclass(frozen=True)
class ScoringResult:
    composite_score: float
    risk_band: str
    ci_score: float
    defect_driver_score: float
    reactive_score: float
    edi_score: float
    dominant_defect_driver: Optional[str]
    treatment_recommendation: str
    scoring_version: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rci_band(ci: Optional[float]) -> str:
    if ci is None:
        return "Unknown"
    if ci < settings.ci_green_threshold:
        return "Green"
    if ci < settings.ci_amber_threshold:
        return "Amber"
    return "Red"


def _risk_band(score: float) -> str:
    if score >= settings.risk_critical:
        return "Critical"
    if score >= settings.risk_high:
        return "High"
    if score >= settings.risk_medium:
        return "Medium"
    return "Low"


def _tz(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


# ── Component scorers ─────────────────────────────────────────────────────────

def _ci_score(
    avg_ci: Optional[float],
    red_pct: Optional[float] = None,
    amber_pct: Optional[float] = None,
) -> float:
    """
    CI condition score (0–40 pts).

    Band classification follows the UKPMS/WSCC standard:
      RED:   section has red_pct > 0  (contains 10m intervals scoring ≥ 100)
      AMBER: section has amber_pct > 0 AND red_pct == 0
      GREEN: no red or amber lengths present

    This is the correct interpretation — most sections will never average ≥ 100
    even if they contain red lengths.  avg_ci measures severity/deterioration
    within the band, not the band itself.

    Falls back to avg_ci thresholds when band-penetration data are unavailable.
    """
    has_red   = red_pct   is not None and red_pct   > 0
    has_amber = amber_pct is not None and amber_pct > 0

    # ── Red band (25–40 pts) ──────────────────────────────────────────────────
    if has_red or (red_pct is None and avg_ci is not None and avg_ci >= settings.ci_amber_threshold):
        # Extent: how much of the section is red (capped at 50 % = max severity)
        extent = min(1.0, (red_pct or 0.1) / 0.50)
        # CI severity: how far avg_ci is into the amber/red territory
        ci_sev = min(1.0, max(0.0, ((avg_ci or 40) - 40) / 110.0))
        return 25.0 + (extent * 0.65 + ci_sev * 0.35) * (settings.ci_red_max - settings.ci_amber_max)

    # ── Amber band (10–25 pts) ────────────────────────────────────────────────
    if has_amber or (amber_pct is None and avg_ci is not None and avg_ci >= settings.ci_green_threshold):
        extent = min(1.0, (amber_pct or 0.1) / 0.80)
        ci_sev = min(1.0, max(0.0, ((avg_ci or 40) - 40) / 60.0))
        return settings.ci_green_max + (extent * 0.5 + ci_sev * 0.5) * (settings.ci_amber_max - settings.ci_green_max)

    # ── Green band (0–10 pts) ─────────────────────────────────────────────────
    return min(settings.ci_green_max, ((avg_ci or 0) / settings.ci_green_threshold) * settings.ci_green_max)


def _defect_driver_score(
    ci_rutting: Optional[float],
    ci_cracking: Optional[float],
    ci_texture: Optional[float],
    ci_lpv: Optional[float],
    red_pct: Optional[float],
    amber_pct: Optional[float],
) -> tuple[float, Optional[str]]:
    """
    Analyse CI contribution proportions to determine intervention type.
    Returns (score 0–30, dominant_driver_name).
    """
    contribs = {
        "LPV": ci_lpv or 0.0,
        "Rutting": ci_rutting or 0.0,
        "Cracking": ci_cracking or 0.0,
        "Texture": ci_texture or 0.0,
    }

    if not any(contribs.values()):
        return 0.0, None

    dominant_key = max(contribs, key=contribs.__getitem__)
    dominant_val = contribs[dominant_key]
    score = 0.0

    # Points for dominant driver exceeding threshold
    if dominant_key == "LPV" and dominant_val > settings.dd_lpv_threshold:
        score += settings.dd_lpv_points
    elif dominant_key == "Rutting" and dominant_val > settings.dd_rutting_threshold:
        score += settings.dd_rutting_points
    elif dominant_key == "Cracking" and dominant_val > settings.dd_cracking_threshold:
        score += settings.dd_cracking_points
    elif dominant_key == "Texture" and dominant_val > settings.dd_texture_threshold:
        score += settings.dd_texture_points

    # Band penetration bonuses
    if red_pct is not None and red_pct > settings.dd_high_red_threshold:
        score += settings.dd_high_red_points
    if amber_pct is not None and amber_pct > settings.dd_high_amber_threshold:
        score += settings.dd_high_amber_points

    return min(30.0, score), dominant_key


def _edi_score(edi: Optional[float]) -> float:
    """EDI score (0–15), B+C roads only."""
    if edi is None:
        return 0.0
    if edi < settings.edi_low_threshold:
        return 0.0
    if edi < settings.edi_mid_threshold:
        return settings.edi_low_points
    if edi < settings.edi_high_threshold:
        return settings.edi_mid_points
    return settings.edi_high_points


def _reactive_score(jobs: List[dict]) -> float:
    """Recency-weighted reactive job frequency score (0–15)."""
    if not jobs:
        return 0.0
    now = datetime.now(tz=timezone.utc)
    cutoff_12m = now - timedelta(days=settings.reactive_lookback_months * 30)
    cutoff_6m = now - timedelta(days=settings.reactive_emergency_lookback_months * 30)

    jobs_12m = [
        j for j in jobs
        if j.get("job_date") and _tz(j["job_date"]) >= cutoff_12m
    ]
    emergency_6m = [
        j for j in jobs_12m
        if str(j.get("response_category", "")).lower() in ("emergency", "24hr", "24 hr", "emergency (24hr)")
        and _tz(j["job_date"]) >= cutoff_6m
    ]

    job_s = min(settings.reactive_job_max, len(jobs_12m) * settings.reactive_job_points)
    emrg_s = min(settings.reactive_emergency_max, len(emergency_6m) * settings.reactive_emergency_points)
    return job_s + emrg_s


# ── Treatment recommendation ──────────────────────────────────────────────────

def _treatment(avg_ci: Optional[float], driver: Optional[str], road_name: Optional[str]) -> str:
    name = (road_name or "").upper()

    if avg_ci is None:
        rec = "No survey data — survey required before intervention decision"
    elif avg_ci < 40:
        if driver == "Texture":
            rec = "Surface dressing / thin surfacing"
        elif driver in ("LPV", "Cracking"):
            rec = "Monitor — structure appears sound, surface treatment within 1–2 years"
        else:
            rec = "Monitor — low CI, programme surface treatment when opportune"
    elif avg_ci < 65:
        if driver == "Texture":
            rec = "Thin surfacing — confirm structural strength (FWD recommended)"
        elif driver in ("LPV", "Rutting"):
            rec = "Inlay (mill and fill) — structural investigation recommended"
        else:
            rec = "Thin surfacing or inlay — investigate defect origin before committing"
    elif avg_ci < 100:
        rec = "Overlay or reconstruction — structural investigation required"
    else:
        rec = "Urgent reconstruction — prioritise for capital programme"

    if "ROUNDABOUT" in name:
        rec += " — high stress site, consider SMA surface"

    return rec


# ── Public scoring functions ──────────────────────────────────────────────────

def compute_scanner_score(
    avg_ci: Optional[float],
    ci_contribution_rutting: Optional[float],
    ci_contribution_cracking: Optional[float],
    ci_contribution_texture: Optional[float],
    ci_contribution_lpv: Optional[float],
    red_pct: Optional[float],
    amber_pct: Optional[float],
    edi_avg: Optional[float],
    reactive_jobs: List[dict],
    road_name: Optional[str] = None,
) -> ScoringResult:
    ci_s = _ci_score(avg_ci, red_pct, amber_pct)
    dd_s, driver = _defect_driver_score(
        ci_contribution_rutting,
        ci_contribution_cracking,
        ci_contribution_texture,
        ci_contribution_lpv,
        red_pct,
        amber_pct,
    )
    edi_s = _edi_score(edi_avg)
    react_s = _reactive_score(reactive_jobs)
    composite = ci_s + dd_s + edi_s + react_s

    return ScoringResult(
        composite_score=round(composite, 2),
        risk_band=_risk_band(composite),
        ci_score=round(ci_s, 2),
        defect_driver_score=round(dd_s, 2),
        reactive_score=round(react_s, 2),
        edi_score=round(edi_s, 2),
        dominant_defect_driver=driver,
        treatment_recommendation=_treatment(avg_ci, driver, road_name),
        scoring_version=settings.scoring_version,
    )


def compute_cvi_score(
    structural_ci: Optional[float],
    edge_ci: Optional[float],
    wearing_course_ci: Optional[float],
    reactive_jobs: List[dict],
) -> ScoringResult:
    ci_s = 0.0
    driver_parts = []

    if structural_ci is not None:
        if structural_ci >= 85:
            ci_s += 40.0
            driver_parts.append(("Structural", 40.0))
        elif structural_ci >= 70:
            ci_s += 25.0
            driver_parts.append(("Structural", 25.0))

    if edge_ci is not None:
        if edge_ci >= 50:
            ci_s += 20.0
            driver_parts.append(("Edge", 20.0))
        elif edge_ci >= 35:
            ci_s += 10.0
            driver_parts.append(("Edge", 10.0))

    if wearing_course_ci is not None:
        if wearing_course_ci >= 60:
            ci_s += 15.0
            driver_parts.append(("WearingCourse", 15.0))
        elif wearing_course_ci >= 45:
            ci_s += 8.0
            driver_parts.append(("WearingCourse", 8.0))

    react_s = _reactive_score(reactive_jobs)
    composite = ci_s + react_s
    dominant = driver_parts[0][0] if driver_parts else None

    if dominant == "Structural":
        rec = "Structural investigation required — consider reconstruction or overlay"
    elif dominant == "Edge":
        rec = "Edge repair — vegetation clearance, edge regrading, check drainage"
    elif dominant == "WearingCourse":
        rec = "Surface treatment — micro-asphalt or surface dressing"
    else:
        rec = "Monitor — condition within acceptable limits"

    return ScoringResult(
        composite_score=round(composite, 2),
        risk_band=_risk_band(composite),
        ci_score=round(ci_s, 2),
        defect_driver_score=0.0,
        reactive_score=round(react_s, 2),
        edi_score=0.0,
        dominant_defect_driver=dominant,
        treatment_recommendation=rec,
        scoring_version=settings.scoring_version,
    )


def no_data_score() -> ScoringResult:
    return ScoringResult(
        composite_score=0.0,
        risk_band="Low",
        ci_score=0.0,
        defect_driver_score=0.0,
        reactive_score=0.0,
        edi_score=0.0,
        dominant_defect_driver=None,
        treatment_recommendation="No survey data — survey required",
        scoring_version=settings.scoring_version,
    )
