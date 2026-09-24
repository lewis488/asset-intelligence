import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.asset import AnalysisRun, Asset, RiskScore
from models.user import Authority, User
from routers.auth import get_current_user, require_contributor, resolve_authority_id
from schemas.asset import AnalysisRunOut, QueryRequest, QueryResponse
from services.llm import answer_query, generate_analysis, generate_vaisala_section_narrative
from services.vaisala_treatments import ASSESSMENT_INPUTS
from config import settings

router = APIRouter(prefix="/analysis", tags=["analysis"])
logger = logging.getLogger(__name__)


def _build_scored_assets(authority_id: Optional[int], db: Session) -> tuple[list[dict], dict]:
    """
    Score all assets for an authority and return:
      (scored_list sorted by composite_score desc, stats_dict)
    authority_id=None means all authorities (admin only).
    """
    from routers.assets import _score_asset  # avoid circular at module level
    from sqlalchemy import text as _text

    q = db.query(Asset)
    if authority_id is not None:
        q = q.filter(Asset.authority_id == authority_id)
    assets = q.all()
    scored: list[dict] = []
    scanner_count = cvi_count = scrim_count = reactive_count = 0
    ci_values: list[float] = []
    band_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}

    # RCI condition band accumulators — band from rci_band column, length from network_assets
    rci_red_count = rci_amber_count = rci_green_count = 0
    total_red_m = total_amber_m = 0.0

    # network_assets is authoritative for length (assets.length_m is often NULL)
    na_rows = db.execute(_text("""
        SELECT nsg_ref, length_m
        FROM network_assets
        WHERE (:auth_id IS NULL OR authority_id = :auth_id)
    """), {"auth_id": authority_id}).fetchall()
    na_length_by_nsg: dict[str, float] = {r[0]: (r[1] or 0.0) for r in na_rows}
    total_network_m = float(sum(r[1] or 0 for r in na_rows))

    # SCANNER covers A/B/C only — use classified length as denominator for red/amber %
    classified_m_row = db.execute(_text("""
        SELECT COALESCE(SUM(length_m), 0)
        FROM network_assets
        WHERE (:auth_id IS NULL OR authority_id = :auth_id)
          AND road_class IN ('A', 'B', 'C')
    """), {"auth_id": authority_id}).scalar()
    classified_network_m = float(classified_m_row or 0)

    for asset in assets:
        row = _score_asset(asset, db)
        scored.append(row)

        if row["has_scanner"]:
            scanner_count += 1
            sd = row["scanner_data"]
            avg_ci = sd.get("avg_ci") if sd else None
            if avg_ci is not None:
                ci_values.append(avg_ci)

            rci_band = sd.get("rci_band") if sd else None
            length_m = na_length_by_nsg.get(row["nsg_ref"]) or 0.0
            if rci_band == "Red":
                rci_red_count += 1
                red_pct = sd.get("red_pct") or 0.0
                total_red_m += (red_pct / 100.0) * length_m
            elif rci_band == "Amber":
                rci_amber_count += 1
                amber_pct = sd.get("amber_pct") or 0.0
                total_amber_m += (amber_pct / 100.0) * length_m
            else:
                rci_green_count += 1

        if row["has_cvi"]:
            cvi_count += 1
        if row["has_scrim"]:
            scrim_count += 1
        if row["has_reactive"]:
            reactive_count += 1

        band = row["risk_band"]
        band_counts[band] = band_counts.get(band, 0) + 1

    scored.sort(key=lambda x: x["composite_score"], reverse=True)

    def _pct(n: int) -> Optional[float]:
        return round(n / scanner_count * 100, 1) if scanner_count else None

    stats = {
        "total_assets": len(assets),
        "scanner_count": scanner_count,
        "cvi_count": cvi_count,
        "scrim_count": scrim_count,
        "reactive_count": reactive_count,
        "critical_count": band_counts["Critical"],
        "high_count": band_counts["High"],
        "medium_count": band_counts["Medium"],
        "low_count": band_counts["Low"],
        "avg_ci": round(sum(ci_values) / len(ci_values), 1) if ci_values else None,
        "rci_red_count":   rci_red_count,
        "rci_amber_count": rci_amber_count,
        "rci_green_count": rci_green_count,
        "rci_red_pct":     _pct(rci_red_count),
        "rci_amber_pct":   _pct(rci_amber_count),
        "rci_green_pct":   _pct(rci_green_count),
        "total_red_km":      round(total_red_m   / 1000, 2),
        "total_amber_km":    round(total_amber_m / 1000, 2),
        "total_network_km":         round(total_network_m    / 1000, 2),
        "classified_network_km":    round(classified_network_m / 1000, 2),
        # % of classified (A/B/C) network — SCANNER does not cover D roads
        "red_network_pct":   round(total_red_m   / classified_network_m * 100, 1) if classified_network_m else None,
        "amber_network_pct": round(total_amber_m / classified_network_m * 100, 1) if classified_network_m else None,
    }

    # ── Vaisala DST: append latest survey summary for AI context ──────────
    # Vaisala programme totals use the complete section cohort, never the top-five sample.
    try:
        from sqlalchemy import func as _func, case as _case
        from models.vaisala import VaisalaSurvey as _VS, VaisalaSection as _VSec

        vq = db.query(_VS)
        if authority_id is not None:
            vq = vq.filter(_VS.authority_id == authority_id)
        latest_vaisala = vq.order_by(_VS.imported_at.desc()).first()
        if latest_vaisala:
            from routers.vaisala import _build_view_rows
            from routers.vaisala_programme import _policy
            from services.vaisala_programme import build_programme
            programme = build_programme(
                _build_view_rows(db, latest_vaisala.id, 'section', 'combined', include_unknown=True, assess=False),
                survey_id=latest_vaisala.id, policy=_policy(db, latest_vaisala.authority_id))
            programme_by_section = {item['section_ref']: item for item in programme['items']}
            agg = db.query(
                _func.count(_VSec.id).label("total"),
                _func.coalesce(_func.sum(_VSec.length_m), 0).label("total_m"),
                _func.coalesce(_func.sum(
                    _case((_VSec.rag_band == "Red", _VSec.length_m), else_=0)
                ), 0).label("red_m"),
                _func.coalesce(_func.sum(
                    _case((_VSec.rag_band == "Amber", _VSec.length_m), else_=0)
                ), 0).label("amber_m"),
                _func.coalesce(_func.sum(
                    _case((_VSec.rag_band == "Red", 1), else_=0)
                ), 0).label("red_count"),
                _func.coalesce(_func.sum(
                    _case((_VSec.rag_band == "Amber", 1), else_=0)
                ), 0).label("amber_count"),
                _func.coalesce(_func.sum(
                    _case((_VSec.rag_band == "Green", 1), else_=0)
                ), 0).label("green_count"),
            ).filter(_VSec.survey_id == latest_vaisala.id).one()

            top5 = (
                db.query(_VSec)
                .filter_by(survey_id=latest_vaisala.id)
                .order_by(_VSec.priority_score.desc().nullslast())
                .limit(5)
                .all()
            )

            stats["vaisala_stats"] = {
                "survey_id":        latest_vaisala.id,
                "source_filename":  latest_vaisala.source_filename,
                "network_key":      latest_vaisala.network_key,
                "has_weight_drift": latest_vaisala.has_weight_drift,
                "section_count":    agg.total,
                "total_km":         round(agg.total_m / 1000, 2),
                "red_count":        agg.red_count,
                "amber_count":      agg.amber_count,
                "green_count":      agg.green_count,
                "red_km":           round(agg.red_m / 1000, 2),
                "amber_km":         round(agg.amber_m / 1000, 2),
                "programme_summary": programme['summary'],
                "programme_model_version": programme['model_version'],
                "programme_policy_version": programme['policy_version'],
                "top5_sections": [
                    {
                        "section_ref":                 s.section_ref,
                        "road_name":                   s.road_name,
                        "priority_score":              s.priority_score,
                        "rag_band":                    s.rag_band,
                        "treatment_assessment":        programme_by_section[s.section_ref]['treatment_assessment'],
                        "programme_item_key":          programme_by_section[s.section_ref]['item_key'],
                        "programme_brief":             programme_by_section[s.section_ref]['brief'],
                        "programme_priority":          programme_by_section[s.section_ref]['priority_explanation'],
                        "primary_defect":              s.primary_defect,
                        "primary_defect_contribution": s.primary_defect_contribution,
                    }
                    for s in top5
                ],
            }
    except Exception:
        logger.exception("Failed to load Vaisala stats for authority %s — dashboard unaffected", authority_id)

    return scored, stats


def _persist_scores(scored: list[dict], db: Session):
    """Upsert latest risk scores into risk_scores table."""
    now = datetime.now(tz=timezone.utc)
    for row in scored:
        asset_id = row["id"]
        db.query(RiskScore).filter(RiskScore.asset_id == asset_id).delete()
        rs = RiskScore(
            asset_id=asset_id,
            scored_at=now,
            composite_score=row["composite_score"],
            risk_band=row["risk_band"],
            ci_score=row["scanner_score"],          # scanner is the CI-based component
            defect_driver_score=row["cvi_score"],   # CVI is the second structural pathway
            reactive_score=row["reactive_score"],
            edi_score=row["scrim_score"],            # reuse edi_score column for SCRIM
            dominant_defect_driver=row["dominant_dataset"],
            treatment_recommendation=row.get("treatment_recommendation"),
            urgency=row.get("urgency"),
            confidence=row.get("confidence"),
            scoring_version=settings.scoring_version,
        )
        db.add(rs)


@router.post("/run", response_model=AnalysisRunOut)
def run_analysis(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_contributor),
):
    # Deletion locks the same authority. Hold this until results are persisted so an
    # in-flight analysis cannot recreate scores from inputs that were just deleted.
    authority = db.query(Authority).filter(Authority.id == current_user.authority_id).with_for_update().first()
    if authority is None:
        raise HTTPException(status_code=404, detail="Authority not found")
    scored, stats = _build_scored_assets(current_user.authority_id, db)

    if not scored:
        raise HTTPException(
            status_code=400,
            detail="No asset data loaded. Upload SCANNER, CVI, or reactive data first.",
        )

    try:
        summary = generate_analysis(scored, stats)
    except Exception as exc:
        logger.error("LLM analysis error: %s", exc)
        raise HTTPException(status_code=502, detail=f"AI analysis failed: {exc}")

    _persist_scores(scored, db)

    run = AnalysisRun(
        authority_id=current_user.authority_id,
        summary_text=summary,
        priority_list_json=scored[:50],
        parameters_used={
            "scoring_version": settings.scoring_version,
            "total_assets": stats["total_assets"],
            "stats": stats,
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get("/latest", response_model=AnalysisRunOut)
def latest_analysis(
    authority_id: Optional[int] = Query(None, description="Admin only — filter by authority"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    auth_id = resolve_authority_id(current_user, authority_id)
    q = db.query(AnalysisRun)
    if auth_id is not None:
        q = q.filter(AnalysisRun.authority_id == auth_id)
    run = q.order_by(AnalysisRun.created_at.desc()).first()
    if not run:
        raise HTTPException(status_code=404, detail="No analysis runs found. Run an analysis first.")
    return run


@router.post("/query", response_model=QueryResponse)
def query(
    req: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_contributor),
):
    scored, stats = _build_scored_assets(current_user.authority_id, db)
    if not scored:
        raise HTTPException(status_code=400, detail="No asset data loaded.")

    try:
        ans = answer_query(req.question, scored, stats, req.conversation_history)
    except Exception as exc:
        logger.error("LLM query error: %s", exc)
        raise HTTPException(status_code=502, detail=f"AI query failed: {exc}")

    return {"question": req.question, "answer": ans}


@router.get("/stats")
def stats(
    authority_id: Optional[int] = Query(None, description="Admin only — filter by authority"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """KPI stats for the dashboard — no LLM call."""
    auth_id = resolve_authority_id(current_user, authority_id)
    _, stats_dict = _build_scored_assets(auth_id, db)
    return stats_dict


# ── Per-asset narrative ───────────────────────────────────────────────────────

_narrative_cache: dict = {}


@router.post("/asset/{nsg_ref}")
def asset_narrative(
    nsg_ref: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_contributor),
):
    """Generate a 3–4 sentence AI narrative for a single asset. Cached per asset per day."""
    from datetime import date as _date
    from routers.assets import _score_asset
    from services.llm import generate_asset_narrative

    auth_id = resolve_authority_id(current_user, None)
    cache_key = (nsg_ref, auth_id, _date.today().isoformat())
    q = db.query(Asset).filter(Asset.nsg_ref == nsg_ref)
    if auth_id is not None:
        q = q.filter(Asset.authority_id == auth_id)
    asset = q.first()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {nsg_ref!r} not found")

    row = _score_asset(asset, db)

    parts = [
        f"{row['road_name'] or 'Unknown road'} "
        f"({row.get('road_class') or '?'}, {row.get('parish') or 'unknown parish'})"
    ]
    data_used = []

    if row.get("scanner_data"):
        sd = row["scanner_data"]
        parts.append(
            f"SCANNER {sd.get('survey_year')}: CI={sd.get('avg_ci')}, {sd.get('rci_band')}, "
            + (f"red_pct={sd['red_pct']:.2f}%" if sd.get('red_pct') is not None else "red_pct=unknown")
        )
        data_used.append("SCANNER")

    if row.get("cvi_data"):
        cd = row["cvi_data"]
        parts.append(
            f"CVI {cd.get('survey_year')}: structural={cd.get('max_ci_structural')}, "
            f"edge={cd.get('max_ci_edge')}, wearingcourse={cd.get('max_ci_wearingcourse')}, "
            f"any_flagged={'yes' if cd.get('any_flagged') else 'no'}"
        )
        data_used.append("CVI")

    if row.get("scrim_data"):
        scr = row["scrim_data"]
        parts.append(
            f"SCRIM {scr.get('survey_year')}: mean_sfc={scr.get('mean_sfc')}, "
            f"IL_threshold={scr.get('sfct_threshold')}, "
            f"{'BELOW' if scr.get('safety_flagged') else 'above'} investigatory level, "
            + (f"pct_below_il={scr['pct_below_il']:.2f}%" if scr.get('pct_below_il') is not None else "pct_below_il=unknown")
        )
        data_used.append("SCRIM")

    if row.get("reactive_data"):
        rd = row["reactive_data"]
        parts.append(
            f"Reactive {rd.get('year')}: {rd.get('total_jobs_raised')} jobs, "
            f"{rd.get('pothole_count', 0)} potholes, "
            f"last defect {rd.get('days_since_most_recent_defect')} days ago"
        )
        data_used.append("Reactive")

    parts.append(f"Indicative screening output: {row.get('treatment_recommendation', 'Not assessed')}")
    parts.append(f"Screening priority (not an approved works deadline): {row.get('urgency', 'Not assessed')}")
    parts.append(f"Composite score: {row.get('composite_score')} ({row.get('risk_band')})")

    context = "\n".join(parts)

    # Re-read inputs before cache lookup: deleted uploads must not survive in a worker's cache.
    cache_key = (*cache_key, context)
    if cache_key in _narrative_cache:
        return {**_narrative_cache[cache_key], "cached": True}

    try:
        narrative = generate_asset_narrative(context)
    except Exception as exc:
        logger.error("Asset narrative error for %s: %s", nsg_ref, exc)
        raise HTTPException(status_code=502, detail=f"AI narrative failed: {exc}")

    result = {
        "narrative": narrative,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "data_used": data_used,
    }
    _narrative_cache[cache_key] = result
    return {**result, "cached": False}


@router.post("/vaisala/{section_id}")
def vaisala_section_narrative(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_contributor),
):
    """Generate a 3–4 sentence AI assessment for a single Vaisala section. Cached per section per day."""
    from datetime import date as _date
    from models.vaisala import VaisalaSection as _VSec, VaisalaSurvey as _VS

    auth_id = resolve_authority_id(current_user, None)
    cache_key = ("vaisala", section_id, auth_id, _date.today().isoformat())
    q = db.query(_VSec).join(_VS, _VSec.survey_id == _VS.id).filter(_VSec.id == section_id)
    if auth_id is not None:
        q = q.filter(_VS.authority_id == auth_id)
    section = q.first()
    if not section:
        raise HTTPException(status_code=404, detail=f"Vaisala section {section_id} not found")

    survey = db.query(_VS).filter_by(id=section.survey_id).first()

    def _fmt(v, d=2):
        return f"{v:.{d}f}" if v is not None else "—"

    parts = [
        f"Road section: {section.section_ref}" + (f" — {section.road_name}" if section.road_name else ""),
        "Network: " + survey.network_key
        + (f" | Length: {_fmt(section.length_m, 0)}m" if section.length_m else "")
        + (f" | Class: {section.road_class}" if section.road_class else "")
        + (f" | {section.urban_rural}" if section.urban_rural else ""),
        f"Vaisala List 4 weighted priority score: {_fmt(section.priority_score)}"
        + (f" | Worst interval score: {_fmt(section.worst_interval_score)}" if section.worst_interval_score else ""),
        "RAG band: " + (section.rag_band or "—")
        + " (Red ≥ 4.0 · Amber ≥ 1.8 — fixed evidence-derived thresholds, not percentile ranks)"
        + (
            " ⚠ WEIGHT DRIFT: defect weights used for scoring differ from those against which the "
            "thresholds were derived — RAG banding for this section should be treated as indicative only."
            if survey.has_weight_drift else ""
        ),
        "Structural capacity, drainage cause, site inspection and treatment approval: not supplied in this context.",
    ]

    import json
    from services.vaisala_programme import programme_item
    from routers.vaisala_programme import _policy
    item = programme_item({**{key: getattr(section, key, None) for key in ASSESSMENT_INPUTS},
                           'id': section.id, 'section_ref': section.section_ref,
                           'net_reference': section.net_reference,
                           'length_m': section.length_m, 'assessment_scope': 'section'},
                          survey_id=survey.id, policy=_policy(db, survey.authority_id))
    assessment = item['treatment_assessment']
    parts.append('Structured treatment assessment (whole section): ' + json.dumps(assessment))
    parts.append('Deterministic action programme (whole-section preview, not a saved client decision): ' + json.dumps({
        key: item[key] for key in ('item_key', 'model_version', 'policy_version', 'recommended_action',
                                   'brief', 'next_question', 'prerequisite_tasks', 'evidence_status')}))
    parts.append('Do not invent a queue rank: this individual section context does not include its complete cohort. Survey acquisition date is not established by the import date.')

    if section.primary_defect:
        contr = f" (score contribution: {_fmt(section.primary_defect_contribution, 4)} units)" if section.primary_defect_contribution else ""
        parts.append(f"Primary defect: {section.primary_defect}{contr}")
    if section.secondary_defect:
        contr = f" (score contribution: {_fmt(section.secondary_defect_contribution, 4)} units)" if section.secondary_defect_contribution else ""
        parts.append(f"Secondary defect: {section.secondary_defect}{contr}")

    # Defect-group proportions (stored as 0–100)
    grp_parts = []
    for label, attr in [
        ("Structural", "structural_pct"), ("Localised", "localised_pct"),
        ("Surface Dressing", "dressing_pct"), ("Micro-surfacing", "micro_pct"),
        ("Alligator cracking", "alligator_pct"), ("Edge deterioration", "edge_pct"),
    ]:
        v = getattr(section, attr, None)
        if v is not None:
            grp_parts.append(f"{label}={v:.1f}%")
    if grp_parts:
        parts.append("Defect group proportions (whole percentages; length-weighted group measures, not suitability probabilities): " + " · ".join(grp_parts))
        parts.append("Groups can overlap. Structural is a defect grouping, not confirmed structural failure.")

    if section.defect_proportions:
        parts.append("Individual defect proportions (whole percentages): " + " · ".join(
            f"{name}={value:.1f}%" for name, value in section.defect_proportions.items()
            if value is not None
        ))

    # Native Vaisala scores
    native = []
    if section.road_surface_condition is not None:
        native.append(f"RSC={_fmt(section.road_surface_condition)}"
                      + (f" (Class {section.road_surface_condition_class})" if section.road_surface_condition_class else ""))
    if section.asphalt_condition is not None:
        native.append(f"Asphalt={_fmt(section.asphalt_condition)}"
                      + (f" (Class {section.asphalt_condition_class})" if section.asphalt_condition_class else ""))
    if section.pas2161_category is not None:
        native.append(f"PAS 2161 category={section.pas2161_category}")
    if native:
        parts.append("Vaisala native condition scores: " + " · ".join(native))

    # QC signals are stored as whole percentages; missing is unknown.
    qc_parts = []
    if section.qc_completeness_pct is not None:
        qc_parts.append(
            f"Completeness={section.qc_completeness_pct:.1f}%"
            + (f" ({section.qc_completeness_band})" if section.qc_completeness_band else "")
        )
    if section.qc_reliability_pct is not None:
        qc_parts.append(
            f"Reliability={section.qc_reliability_pct:.1f}%"
            + (f" ({section.qc_reliability_band})" if section.qc_reliability_band else "")
        )
    if qc_parts:
        parts.append("QC signals: " + " · ".join(qc_parts))
        if section.qc_completeness_pct is None or section.qc_reliability_pct is None:
            parts.append("One QC metric is missing: its quality is unknown.")
        low_qc = (section.qc_completeness_band == "Low") or (section.qc_reliability_band == "Low")
        if low_qc:
            parts.append(
                "⚠ One or more QC signals are Low — this section's score and treatment should be "
                "treated as provisional pending video validation."
            )
    else:
        parts.append("QC signals: unknown (not supplied).")
    parts.append("QC measures survey coverage and validity, not diagnostic certainty or treatment suitability.")

    context = "\n".join(parts)

    cache_key = (*cache_key, context)
    if cache_key in _narrative_cache:
        return {**_narrative_cache[cache_key], "cached": True}

    try:
        narrative = generate_vaisala_section_narrative(context)
    except Exception as exc:
        logger.error("Vaisala section narrative error for section %d: %s", section_id, exc)
        raise HTTPException(status_code=502, detail=f"AI narrative failed: {exc}")

    result = {
        "narrative": narrative,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "section_ref": section.section_ref,
    }
    _narrative_cache[cache_key] = result
    return {**result, "cached": False}
