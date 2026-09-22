import asyncio
import csv
import io
import logging
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
from models.asset import Asset, CviRecord, ReactiveJob, ScannerRecord
from models.user import User
from routers.auth import get_current_user, require_contributor, resolve_authority_id
from schemas.asset import AssetWithScore, IngestionResult, PaginatedAssets
from services.ingestion import (
    SCANNER_CSV_COLUMNS,
    get_alias_reference,
    parse_cvi_csv,
    parse_reactive_csv,
    parse_scanner_csv,
    parse_scanner_excel,
)
from models.asset import CviRawRecord, ScrimRecord, ScannerRawRecord
from models.asset import ReactiveJobRecord, ReactiveAggregate
from models.asset import NetworkAsset
from services.ingestion import parse_cvi_raw, parse_scanner_raw, parse_scrim_raw
from services.ingestion import parse_reactive_raw
from services.ingestion import parse_network_file
from schemas.asset import RawIngestionResult, ReactiveRawIngestionResult, NetworkIngestionResult
from services.validation import DatasetValidator, read_tabular_for_validation, read_network_for_validation
from dataset_schemas import (
    SCANNER_RAW_SCHEMA, CVI_RAW_SCHEMA, SCRIM_RAW_SCHEMA,
    REACTIVE_RAW_SCHEMA, NETWORK_SHP_SCHEMA,
)

_validator = DatasetValidator()

router = APIRouter(prefix="/assets", tags=["assets"])
logger = logging.getLogger(__name__)


# ── Scoring helper ────────────────────────────────────────────────────────────

def _score_asset(asset: Asset, db: Session) -> dict:
    scanner = (
        db.query(ScannerRawRecord)
        .filter(ScannerRawRecord.asset_id == asset.id)
        .order_by(ScannerRawRecord.survey_year.desc())
        .first()
    )
    cvi = (
        db.query(CviRawRecord)
        .filter(CviRawRecord.asset_id == asset.id)
        .order_by(CviRawRecord.survey_year.desc())
        .first()
    )
    scrim = (
        db.query(ScrimRecord)
        .filter(ScrimRecord.asset_id == asset.id)
        .order_by(ScrimRecord.survey_year.desc())
        .first()
    )
    reactive = (
        db.query(ReactiveAggregate)
        .filter(ReactiveAggregate.asset_id == asset.id)
        .order_by(ReactiveAggregate.year.desc())
        .first()
    )

    # SCANNER score (0–60 pts)
    if scanner:
        rci = scanner.rci_band or "Green"
        avg_ci = scanner.avg_ci or 0.0
        red_pct = scanner.red_pct or 0.0
        if rci == "Red":
            ci_score = 40.0
        elif rci == "Amber":
            ci_score = 20.0 + (avg_ci / 100.0 * 10.0)
        else:
            ci_score = max(0.0, avg_ci / 10.0)
        scanner_score = ci_score + min(red_pct * 2.0, 20.0)
    else:
        scanner_score = 0.0

    # CVI score (0–65 pts)
    if cvi:
        structural_score = min((cvi.max_ci_structural or 0.0) / 85.0 * 40.0, 40.0)
        edge_score = min((cvi.max_ci_edge or 0.0) / 50.0 * 15.0, 15.0)
        wc_score = min((cvi.max_ci_wearingcourse or 0.0) / 60.0 * 10.0, 10.0)
        cvi_score = structural_score + edge_score + wc_score
    else:
        cvi_score = 0.0

    # SCRIM score (0–30 pts)
    if scrim and scrim.safety_flagged:
        scrim_score = 20.0 + min((scrim.pct_below_il or 0.0), 10.0)
    else:
        scrim_score = 0.0

    # REACTIVE score (0–30 pts)
    if reactive:
        job_score = min((reactive.total_jobs_raised or 0) * 2.0, 15.0)
        emergency_score = min((reactive.emergency_jobs_2hr or 0) * 3.0, 10.0)
        recency_score = 5.0 if (reactive.days_since_most_recent_defect or 999) < 90 else 0.0
        reactive_score = job_score + emergency_score + recency_score
    else:
        reactive_score = 0.0

    composite = scanner_score + cvi_score + scrim_score + reactive_score

    if composite >= 65:
        risk_band = "Critical"
    elif composite >= 40:
        risk_band = "High"
    elif composite >= 20:
        risk_band = "Medium"
    else:
        risk_band = "Low"

    has_scanner = scanner is not None
    has_cvi = cvi is not None
    has_scrim = scrim is not None
    has_reactive = reactive is not None
    datasets_present = sum([has_scanner, has_cvi, has_scrim, has_reactive])
    score_completeness = round(datasets_present / 4 * 100)

    component_scores = {
        "scanner": scanner_score,
        "cvi": cvi_score,
        "scrim": scrim_score,
        "reactive": reactive_score,
    }
    dominant_dataset = max(component_scores, key=component_scores.__getitem__) if datasets_present else None

    years = [
        scanner.survey_year if scanner else None,
        cvi.survey_year if cvi else None,
        scrim.survey_year if scrim else None,
        reactive.year if reactive else None,
    ]
    survey_year = max((y for y in years if y is not None), default=None)

    # ── Treatment recommendation ──────────────────────────────────────────────
    treatment = "No survey data — inspection required"
    urgency = "Survey required"
    cost_low, cost_high = 0, 0

    if scanner:
        _rci = scanner.rci_band or "Green"
        _red = scanner.red_pct or 0.0
        if _rci == "Red" and _red > 15:
            if reactive and (reactive.emergency_jobs_2hr or 0) > 0:
                treatment = "Urgent reconstruction"
                urgency = "Immediate"
                cost_low, cost_high = 80, 150
            else:
                treatment = "Inlay / reconstruction"
                urgency = "This financial year"
                cost_low, cost_high = 45, 80
        elif _rci == "Red" and _red <= 15:
            treatment = "Inlay (mill and fill)"
            urgency = "This financial year"
            cost_low, cost_high = 20, 45
        elif _rci == "Amber" and _red > 25:
            treatment = "Inlay (mill and fill)"
            urgency = "Programme next year"
            cost_low, cost_high = 20, 35
        elif _rci == "Amber" and _red > 10:
            treatment = "Thin surfacing"
            urgency = "Programme next year"
            cost_low, cost_high = 12, 20
        elif _rci == "Amber":
            treatment = "Surface dressing / micro-asphalt"
            urgency = "Monitor and programme"
            cost_low, cost_high = 5, 14
        else:  # Green
            if reactive and (reactive.total_jobs_raised or 0) > 5:
                treatment = "Investigate — reactive masking condition"
                urgency = "Investigate this year"
                cost_low, cost_high = 0, 0
            else:
                treatment = "Monitor"
                urgency = "Routine inspection"
                cost_low, cost_high = 0, 0
    elif cvi:
        if cvi.structural_flagged:
            treatment = "Structural repair / reconstruction"
            urgency = "This financial year"
            cost_low, cost_high = 45, 150
        elif cvi.wearingcourse_flagged:
            treatment = "Surface dressing / micro-asphalt"
            urgency = "Programme next year"
            cost_low, cost_high = 5, 14
        elif cvi.edge_flagged:
            treatment = "Edge treatment"
            urgency = "Programme next year"
            cost_low, cost_high = 25, 38
        else:
            treatment = "Monitor"
            urgency = "Routine inspection"
            cost_low, cost_high = 0, 0

    if scrim and scrim.safety_flagged:
        treatment = treatment + " + Safety: skid resistance treatment"
        urgency = "Immediate"

    if datasets_present >= 3:
        rec_confidence = "High"
    elif datasets_present == 2:
        rec_confidence = "Medium"
    else:
        rec_confidence = "Low"

    return {
        "id": asset.id,
        "nsg_ref": asset.nsg_ref,
        "road_name": asset.road_name,
        "parish": asset.parish,
        "road_class": asset.road_class,
        "length_m": asset.length_m,
        "composite_score": round(composite, 2),
        "risk_band": risk_band,
        "scanner_score": round(scanner_score, 2),
        "cvi_score": round(cvi_score, 2),
        "scrim_score": round(scrim_score, 2),
        "reactive_score": round(reactive_score, 2),
        "has_scanner": has_scanner,
        "has_cvi": has_cvi,
        "has_scrim": has_scrim,
        "has_reactive": has_reactive,
        "score_completeness": score_completeness,
        "dominant_dataset": dominant_dataset,
        "survey_year": survey_year,
        "treatment_recommendation": treatment,
        "urgency": urgency,
        "cost_low_per_m2": cost_low,
        "cost_high_per_m2": cost_high,
        "confidence": rec_confidence,
        "scanner_data": {
            "avg_ci": scanner.avg_ci,
            "rci_band": scanner.rci_band,
            "survey_year": scanner.survey_year,
            "red_pct": scanner.red_pct,
            "amber_pct": scanner.amber_pct,
        } if scanner else None,
        "cvi_data": {
            "max_ci_structural": cvi.max_ci_structural,
            "max_ci_edge": cvi.max_ci_edge,
            "max_ci_wearingcourse": cvi.max_ci_wearingcourse,
            "structural_flagged": cvi.structural_flagged,
            "edge_flagged": cvi.edge_flagged,
            "wearingcourse_flagged": cvi.wearingcourse_flagged,
            "any_flagged": cvi.any_flagged,
            "survey_year": cvi.survey_year,
        } if cvi else None,
        "scrim_data": {
            "safety_flagged": scrim.safety_flagged,
            "pct_below_il": scrim.pct_below_il,
            "worst_xdif": scrim.worst_xdif,
            "mean_sfc": scrim.mean_sfc,
            "sfct_threshold": scrim.sfct_threshold,
            "survey_year": scrim.survey_year,
        } if scrim else None,
        "reactive_data": {
            "total_jobs_raised": reactive.total_jobs_raised,
            "emergency_jobs_2hr": reactive.emergency_jobs_2hr,
            "urgent_jobs_24hr": reactive.urgent_jobs_24hr,
            "pothole_count": reactive.pothole_count,
            "edge_count": reactive.edge_count,
            "mean_days_to_completion": reactive.mean_days_to_completion,
            "days_since_most_recent_defect": reactive.days_since_most_recent_defect,
            "year": reactive.year,
        } if reactive else None,
    }


def _rci_band(red_pct: Optional[float], amber_pct: Optional[float], avg_ci: Optional[float] = None) -> str:
    if (red_pct or 0) > 0:
        return "Red"
    if (amber_pct or 0) > 0:
        return "Amber"
    return "Green"


# ── Upload endpoints ──────────────────────────────────────────────────────────

@router.post("/upload/scanner", response_model=IngestionResult)
async def upload_scanner(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_contributor),
):
    content = await file.read()
    fname = (file.filename or "").lower()
    try:
        if fname.endswith(".csv"):
            result = parse_scanner_csv(content, source_file=file.filename or "upload")
        else:
            result = parse_scanner_excel(content, source_file=file.filename or "upload")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    ingested = 0
    all_mapped: list[str] = []
    all_unmapped: list[str] = []
    sheets_processed: list[str] = []

    for sheet in result.get("sheets", []):
        sheets_processed.append(f"{sheet['sheet_name']} ({sheet['road_class']}): {sheet['rows_ingested']} rows")
        all_mapped.extend(sheet.get("mapped_columns", []))
        all_unmapped.extend(sheet.get("unmapped_columns", []))

    for row in result["records"]:
        nsg = str(row.get("nsg_ref", "")).strip()
        if not nsg:
            continue

        asset = db.query(Asset).filter(
            Asset.authority_id == current_user.authority_id,
            Asset.nsg_ref == nsg,
        ).first()
        if not asset:
            asset = Asset(
                authority_id=current_user.authority_id,
                nsg_ref=nsg,
                road_name=row.get("road_name"),
                parish=row.get("parish"),
                road_class=row.get("road_class"),
                length_m=_safe_float(row.get("length_m")),
            )
            db.add(asset)
            db.flush()
        else:
            if row.get("road_name"): asset.road_name = row["road_name"]
            if row.get("parish"): asset.parish = row["parish"]
            if row.get("road_class") and not asset.road_class: asset.road_class = row["road_class"]

        avg_ci = _safe_float(row.get("avg_ci"))
        length_m = _safe_float(row.get("length_m"))

        # Compute amber_pct and red_pct if missing but lengths available
        amber_pct = _safe_float(row.get("amber_pct"))
        red_pct = _safe_float(row.get("red_pct"))
        if amber_pct is None and length_m:
            al = _safe_float(row.get("amber_length_m"))
            amber_pct = (al / length_m) if al is not None else None
        if red_pct is None and length_m:
            rl = _safe_float(row.get("red_length_m"))
            red_pct = (rl / length_m) if rl is not None else None

        record = ScannerRecord(
            asset_id=asset.id,
            survey_year=_safe_int(row.get("survey_year")),
            avg_ci=avg_ci,
            rci_band=_rci_band(red_pct, amber_pct, avg_ci),
            defect_overall_pct=_safe_float(row.get("defect_overall_pct")),
            defect_rutting_pct=_safe_float(row.get("defect_rutting_pct")),
            defect_cracking_pct=_safe_float(row.get("defect_cracking_pct")),
            defect_texture_pct=_safe_float(row.get("defect_texture_pct")),
            defect_lpv_pct=_safe_float(row.get("defect_lpv_pct")),
            amber_length_m=_safe_float(row.get("amber_length_m")),
            amber_pct=amber_pct,
            amber_rutting=_safe_float(row.get("amber_rutting")),
            amber_cracking=_safe_float(row.get("amber_cracking")),
            amber_texture=_safe_float(row.get("amber_texture")),
            amber_lpv=_safe_float(row.get("amber_lpv")),
            red_length_m=_safe_float(row.get("red_length_m")),
            red_pct=red_pct,
            red_rutting=_safe_float(row.get("red_rutting")),
            red_cracking=_safe_float(row.get("red_cracking")),
            red_texture=_safe_float(row.get("red_texture")),
            red_lpv=_safe_float(row.get("red_lpv")),
            ci_contribution_rutting=_safe_float(row.get("ci_contribution_rutting")),
            ci_contribution_cracking=_safe_float(row.get("ci_contribution_cracking")),
            ci_contribution_texture=_safe_float(row.get("ci_contribution_texture")),
            ci_contribution_lpv=_safe_float(row.get("ci_contribution_lpv")),
            edi_avg=_safe_float(row.get("edi_avg")),
            source_file=row.get("source_file"),
        )
        db.add(record)
        ingested += 1

    db.commit()
    return IngestionResult(
        ingested_rows=ingested,
        total_rows=len(result["records"]),
        mapped_columns=list(dict.fromkeys(all_mapped)),  # deduplicate
        unmapped_columns=list(dict.fromkeys(all_unmapped)),
        sheets_processed=sheets_processed,
    )


@router.post("/upload/cvi", response_model=IngestionResult)
async def upload_cvi(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_contributor),
):
    content = await file.read()
    try:
        result = parse_cvi_csv(content, source_file=file.filename or "upload")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    ingested = 0
    for row in result["records"]:
        nsg = str(row.get("nsg_ref", "")).strip()
        if not nsg:
            continue

        asset = db.query(Asset).filter(
            Asset.authority_id == current_user.authority_id,
            Asset.nsg_ref == nsg,
        ).first()
        if not asset:
            asset = Asset(
                authority_id=current_user.authority_id,
                nsg_ref=nsg,
                road_name=row.get("road_name"),
                parish=row.get("parish"),
                road_class="U",
                length_m=_safe_float(row.get("length_m")),
            )
            db.add(asset)
            db.flush()

        record = CviRecord(
            asset_id=asset.id,
            survey_year=_safe_int(row.get("survey_year")),
            structural_ci=_safe_float(row.get("structural_ci")),
            edge_ci=_safe_float(row.get("edge_ci")),
            wearing_course_ci=_safe_float(row.get("wearing_course_ci")),
            structural_flagged=bool(row.get("structural_flagged", False)),
            edge_flagged=bool(row.get("edge_flagged", False)),
            wearing_course_flagged=bool(row.get("wearing_course_flagged", False)),
            source_file=row.get("source_file"),
        )
        db.add(record)
        ingested += 1

    db.commit()
    return IngestionResult(
        ingested_rows=ingested,
        total_rows=result["row_count"],
        mapped_columns=result["mapped_columns"],
        unmapped_columns=result["unmapped_columns"],
    )


@router.post("/upload/reactive", response_model=IngestionResult)
async def upload_reactive(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_contributor),
):
    content = await file.read()
    try:
        result = parse_reactive_csv(content, source_file=file.filename or "upload")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    ingested = 0
    for row in result["records"]:
        nsg = str(row.get("nsg_ref", "")).strip()
        if not nsg:
            continue

        asset = db.query(Asset).filter(
            Asset.authority_id == current_user.authority_id,
            Asset.nsg_ref == nsg,
        ).first()
        if not asset:
            asset = Asset(
                authority_id=current_user.authority_id,
                nsg_ref=nsg,
                road_name=row.get("road_name"),
            )
            db.add(asset)
            db.flush()

        job_date = row.get("job_date")
        if hasattr(job_date, "to_pydatetime"):
            job_date = job_date.to_pydatetime()

        job = ReactiveJob(
            asset_id=asset.id,
            nsg_ref=nsg,
            job_ref=row.get("job_ref"),
            job_type=row.get("job_type"),
            defect_type=row.get("defect_type"),
            job_date=job_date,
            cost_gbp=_safe_float(row.get("cost_gbp")),
            response_category=row.get("response_category"),
            source_file=row.get("source_file"),
        )
        db.add(job)
        ingested += 1

    db.commit()
    return IngestionResult(
        ingested_rows=ingested,
        total_rows=result["row_count"],
        mapped_columns=result["mapped_columns"],
        unmapped_columns=result["unmapped_columns"],
    )


# ── Asset list and export ─────────────────────────────────────────────────────

@router.get("/", response_model=PaginatedAssets)
def list_assets(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    risk_band: Optional[str] = Query(None),
    road_class: Optional[str] = Query(None),
    parish: Optional[str] = Query(None),
    authority_id: Optional[int] = Query(None, description="Admin only — filter by authority"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    auth_id = resolve_authority_id(current_user, authority_id)
    q = db.query(Asset)
    if auth_id is not None:
        q = q.filter(Asset.authority_id == auth_id)
    if road_class:
        q = q.filter(Asset.road_class == road_class)
    if parish:
        q = q.filter(Asset.parish.ilike(f"%{parish}%"))
    total = q.count()
    assets_page = q.order_by(Asset.id).offset(skip).limit(limit).all()

    scored = [_score_asset(a, db) for a in assets_page]
    scored.sort(key=lambda x: x["composite_score"], reverse=True)

    if risk_band:
        scored = [a for a in scored if a["risk_band"] == risk_band]

    return {"total": total, "assets": scored}


@router.get("/export")
def export_assets(
    authority_id: Optional[int] = Query(None, description="Admin only — filter by authority"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download full priority list as CSV."""
    auth_id = resolve_authority_id(current_user, authority_id)
    q = db.query(Asset)
    if auth_id is not None:
        q = q.filter(Asset.authority_id == auth_id)
    assets = q.all()
    scored = [_score_asset(a, db) for a in assets]
    scored.sort(key=lambda x: x["composite_score"], reverse=True)

    FIELDS = [
        "nsg_ref", "road_name", "parish", "road_class", "length_m",
        "composite_score", "risk_band",
        "scanner_score", "cvi_score", "scrim_score", "reactive_score",
        "score_completeness", "dominant_dataset", "survey_year",
        "has_scanner", "has_cvi", "has_scrim", "has_reactive",
    ]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FIELDS, extrasaction="ignore")
    writer.writeheader()
    for a in scored:
        writer.writerow({k: a.get(k, "") for k in FIELDS})

    buf.seek(0)
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=priority_list.csv"},
    )


@router.get("/schema/aliases")
def column_aliases():
    return get_alias_reference()


@router.get("/schema/scanner-template")
def scanner_csv_template():
    """Downloadable blank CSV template for SCANNER data."""
    header = ",".join(SCANNER_CSV_COLUMNS) + "\n"
    example = (
        "47001234,A24 HORSHAM ROAD,Horsham,A,450,2024,28.5,"
        "0.18,0.02,0.08,0.08,0.00,"
        "90,0.20,0.01,0.03,0.16,0.00,"
        "0,0.00,0.00,0.00,0.00,0.00,"
        "0.038,0.205,0.434,0.323,\n"
    )
    csv_bytes = io.BytesIO((header + example).encode())
    return StreamingResponse(
        csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=scanner_template.csv"},
    )


# ── Private helpers ───────────────────────────────────────────────────────────

def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        return None if f != f else f  # reject NaN
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> Optional[int]:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


# ── Raw Confirm upload endpoints ──────────────────────────────────────────────

@router.post("/upload/scanner/raw", response_model=RawIngestionResult)
async def upload_scanner_raw(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_contributor),
):
    """Ingest a Confirm SCANNER export (10m interval rows). Aggregates to one record per NSG/year/direction."""
    content = await file.read()
    fname = file.filename or "upload"

    val_result = None
    try:
        val_df = read_tabular_for_validation(content)
        val_result = _validator.validate(val_df, SCANNER_RAW_SCHEMA)
        if not val_result.passed:
            raise HTTPException(status_code=422, detail=val_result.to_dict())
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("SCANNER validation read error: %s", exc)

    try:
        records = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, parse_scanner_raw, content, fname),
            timeout=300.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Processing timed out after 300 s. The file may be too large.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    ingested = 0
    assets_created = 0
    assets_updated = 0
    survey_years: set[int] = set()
    unmapped = records[0].get("_unmapped_columns", []) if records else []

    for rec in records:
        nsg = str(rec["nsg_ref"]).strip()
        if not nsg:
            continue

        asset = db.query(Asset).filter(
            Asset.authority_id == current_user.authority_id,
            Asset.nsg_ref == nsg,
        ).first()
        if not asset:
            asset = Asset(
                authority_id=current_user.authority_id,
                nsg_ref=nsg,
                road_name=rec.get("road_name"),
            )
            db.add(asset)
            db.flush()
            assets_created += 1
        else:
            if rec.get("road_name") and not asset.road_name:
                asset.road_name = rec["road_name"]
            assets_updated += 1

        year = rec["survey_year"]
        dir_ = rec["offset_direction"]

        existing = db.query(ScannerRawRecord).filter(
            ScannerRawRecord.asset_id == asset.id,
            ScannerRawRecord.survey_year == year,
            ScannerRawRecord.offset_direction == dir_,
        ).first()

        fields = {
            "survey_date": rec.get("survey_date"),
            "survey_number": rec.get("survey_number"),
            "total_length_m": rec.get("total_length_m"),
            "avg_ci": rec.get("avg_ci"),
            "red_pct": rec.get("red_pct"),
            "amber_pct": rec.get("amber_pct"),
            "green_pct": rec.get("green_pct"),
            "max_ci": rec.get("max_ci"),
            "min_ci": rec.get("min_ci"),
            "rci_band": rec.get("rci_band"),
            "source_file": rec.get("source_file"),
        }

        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(ScannerRawRecord(asset_id=asset.id, survey_year=year, offset_direction=dir_, **fields))

        ingested += 1
        survey_years.add(year)

    db.commit()
    return RawIngestionResult(
        records_ingested=ingested,
        assets_created=assets_created,
        assets_updated=assets_updated,
        survey_years=sorted(survey_years),
        unmapped_columns=unmapped,
        validation=val_result.to_dict() if val_result else None,
    )


@router.post("/upload/cvi/raw", response_model=RawIngestionResult)
async def upload_cvi_raw(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_contributor),
):
    """Ingest a Confirm CVI export (variable-length sections). Aggregates to one record per NSG/year."""
    content = await file.read()
    fname = file.filename or "upload"

    val_result = None
    try:
        val_df = read_tabular_for_validation(content)
        val_result = _validator.validate(val_df, CVI_RAW_SCHEMA)
        if not val_result.passed:
            raise HTTPException(status_code=422, detail=val_result.to_dict())
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("CVI validation read error: %s", exc)

    try:
        records = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, parse_cvi_raw, content, fname),
            timeout=300.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Processing timed out after 300 s. The file may be too large.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    ingested = 0
    assets_created = 0
    assets_updated = 0
    survey_years: set[int] = set()
    unmapped = records[0].get("_unmapped_columns", []) if records else []

    for rec in records:
        nsg = str(rec["nsg_ref"]).strip()
        if not nsg:
            continue

        asset = db.query(Asset).filter(
            Asset.authority_id == current_user.authority_id,
            Asset.nsg_ref == nsg,
        ).first()
        if not asset:
            asset = Asset(
                authority_id=current_user.authority_id,
                nsg_ref=nsg,
                road_name=rec.get("road_name"),
                parish=rec.get("parish"),
                road_class="U",
            )
            db.add(asset)
            db.flush()
            assets_created += 1
        else:
            if rec.get("road_name") and not asset.road_name:
                asset.road_name = rec["road_name"]
            if rec.get("parish") and not asset.parish:
                asset.parish = rec["parish"]
            assets_updated += 1

        year = rec["survey_year"]

        existing = db.query(CviRawRecord).filter(
            CviRawRecord.asset_id == asset.id,
            CviRawRecord.survey_year == year,
        ).first()

        fields = {
            "survey_date": rec.get("survey_date"),
            "survey_name": rec.get("survey_name"),
            "total_length_m": rec.get("total_length_m"),
            "avg_ci_overall": rec.get("avg_ci_overall"),
            "max_ci_structural": rec.get("max_ci_structural"),
            "max_ci_edge": rec.get("max_ci_edge"),
            "max_ci_wearingcourse": rec.get("max_ci_wearingcourse"),
            "structural_flagged": rec.get("structural_flagged", False),
            "edge_flagged": rec.get("edge_flagged", False),
            "wearingcourse_flagged": rec.get("wearingcourse_flagged", False),
            "any_flagged": rec.get("any_flagged", False),
            "pct_length_structural_flagged": rec.get("pct_length_structural_flagged"),
            "pct_length_edge_flagged": rec.get("pct_length_edge_flagged"),
            "pct_length_wc_flagged": rec.get("pct_length_wc_flagged"),
            "source_file": rec.get("source_file"),
        }

        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(CviRawRecord(asset_id=asset.id, survey_year=year, **fields))

        ingested += 1
        survey_years.add(year)

    db.commit()
    return RawIngestionResult(
        records_ingested=ingested,
        assets_created=assets_created,
        assets_updated=assets_updated,
        survey_years=sorted(survey_years),
        unmapped_columns=unmapped,
        validation=val_result.to_dict() if val_result else None,
    )


@router.post("/upload/scrim/raw", response_model=RawIngestionResult)
async def upload_scrim_raw(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_contributor),
):
    """Ingest a Confirm SCRIM export (10m interval rows). Aggregates to one record per NSG/year."""
    content = await file.read()
    fname = file.filename or "upload"

    val_result = None
    try:
        val_df = read_tabular_for_validation(content)
        val_result = _validator.validate(val_df, SCRIM_RAW_SCHEMA)
        if not val_result.passed:
            raise HTTPException(status_code=422, detail=val_result.to_dict())
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("SCRIM validation read error: %s", exc)

    try:
        records = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, parse_scrim_raw, content, fname),
            timeout=300.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Processing timed out after 300 s. The file may be too large.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    ingested = 0
    assets_created = 0
    assets_updated = 0
    survey_years: set[int] = set()
    unmapped = records[0].get("_unmapped_columns", []) if records else []

    for rec in records:
        nsg = str(rec["nsg_ref"]).strip()
        if not nsg:
            continue

        asset = db.query(Asset).filter(
            Asset.authority_id == current_user.authority_id,
            Asset.nsg_ref == nsg,
        ).first()
        if not asset:
            asset = Asset(
                authority_id=current_user.authority_id,
                nsg_ref=nsg,
                road_name=rec.get("road_name"),
                parish=rec.get("parish"),
            )
            db.add(asset)
            db.flush()
            assets_created += 1
        else:
            if rec.get("road_name") and not asset.road_name:
                asset.road_name = rec["road_name"]
            if rec.get("parish") and not asset.parish:
                asset.parish = rec["parish"]
            assets_updated += 1

        year = rec["survey_year"]

        existing = db.query(ScrimRecord).filter(
            ScrimRecord.asset_id == asset.id,
            ScrimRecord.survey_year == year,
        ).first()

        fields = {
            "survey_date": rec.get("survey_date"),
            "survey_name": rec.get("survey_name"),
            "survey_number": rec.get("survey_number"),
            "total_sections": rec.get("total_sections"),
            "dominant_ilct": rec.get("dominant_ilct"),
            "sfct_threshold": rec.get("sfct_threshold"),
            "mean_sfc": rec.get("mean_sfc"),
            "min_sfc": rec.get("min_sfc"),
            "sections_below_il": rec.get("sections_below_il"),
            "pct_below_il": rec.get("pct_below_il"),
            "safety_flagged": rec.get("safety_flagged", False),
            "worst_xdif": rec.get("worst_xdif"),
            "source_file": rec.get("source_file"),
        }

        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(ScrimRecord(asset_id=asset.id, survey_year=year, **fields))

        ingested += 1
        survey_years.add(year)

    db.commit()
    return RawIngestionResult(
        records_ingested=ingested,
        assets_created=assets_created,
        assets_updated=assets_updated,
        survey_years=sorted(survey_years),
        unmapped_columns=unmapped,
        validation=val_result.to_dict() if val_result else None,
    )


# ── Reactive raw helpers + endpoint ──────────────────────────────────────────

@router.post("/upload/reactive/raw", response_model=ReactiveRawIngestionResult)
async def upload_reactive_raw(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_contributor),
):
    """
    Ingest a Confirm reactive jobs export. Filters to condition-relevant job types,
    deduplicates by job_number, then rebuilds ReactiveAggregate per affected NSG/year.
    """
    content = await file.read()
    fname = file.filename or "upload"

    val_result = None
    try:
        val_df = read_tabular_for_validation(content)
        val_result = _validator.validate(val_df, REACTIVE_RAW_SCHEMA)
        if not val_result.passed:
            raise HTTPException(status_code=422, detail=val_result.to_dict())
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Reactive validation read error: %s", exc)

    try:
        result = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, parse_reactive_raw, content, fname),
            timeout=300.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Processing timed out after 300 s.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    records = result["records"]
    filtered_out = result["filtered_out"]
    job_type_breakdown = result["job_type_breakdown"]

    if not records:
        return ReactiveRawIngestionResult(
            jobs_ingested=0, jobs_skipped=0, jobs_filtered_out=filtered_out,
            assets_created=0, aggregates_rebuilt=0, years_found=[],
            job_type_breakdown=job_type_breakdown,
            validation=val_result.to_dict() if val_result else None,
        )

    existing_job_numbers: set[str] = set(
        r[0] for r in db.query(ReactiveJobRecord.job_number)
        .filter(ReactiveJobRecord.job_number.isnot(None)).all()
    )

    jobs_ingested = 0
    jobs_skipped = 0
    assets_created = 0
    affected: set[tuple] = set()  # (asset_id, year, nsg_ref)

    for rec in records:
        nsg = rec["nsg_ref"]
        job_num = rec.get("job_number")

        if not job_num:
            jobs_skipped += 1
            continue
        if job_num in existing_job_numbers:
            jobs_skipped += 1
            continue

        asset = db.query(Asset).filter(
            Asset.authority_id == current_user.authority_id,
            Asset.nsg_ref == nsg,
        ).first()
        if not asset:
            asset = Asset(
                authority_id=current_user.authority_id,
                nsg_ref=nsg,
                road_name=rec.get("road_name"),
                road_class=rec.get("road_class"),
            )
            db.add(asset)
            db.flush()
            assets_created += 1
        else:
            if rec.get("road_name") and not asset.road_name:
                asset.road_name = rec["road_name"]
            if rec.get("road_class") and not asset.road_class:
                asset.road_class = rec["road_class"]

        db.add(ReactiveJobRecord(
            job_number=job_num,
            asset_id=asset.id,
            nsg_ref=nsg,
            job_entry_date=rec.get("job_entry_date"),
            actual_comp_date=rec.get("actual_comp_date"),
            priority_name=rec.get("priority_name"),
            priority_category=rec.get("priority_category"),
            job_type_name=rec.get("job_type_name"),
            job_type_category=rec.get("job_type_category"),
            status_name=rec.get("status_name"),
            district_name=rec.get("district_name"),
            locality_name=rec.get("locality_name"),
            town_name=rec.get("town_name"),
            road_class=rec.get("road_class"),
            easting=rec.get("easting"),
            northing=rec.get("northing"),
            source_file=rec.get("source_file"),
        ))

        existing_job_numbers.add(job_num)
        jobs_ingested += 1

        entry_dt = rec.get("job_entry_date")
        if entry_dt:
            affected.add((asset.id, entry_dt.year, nsg))

    db.flush()

    # Bulk aggregate rebuild — 2 SQL statements instead of 2 × N queries
    from sqlalchemy import text as _text

    asset_ids = list({t[0] for t in affected})
    years_found = sorted({t[1] for t in affected})

    if asset_ids:
        db.execute(
            _text("DELETE FROM reactive_aggregates WHERE asset_id = ANY(:ids)"),
            {"ids": asset_ids},
        )
        db.execute(_text("""
            INSERT INTO reactive_aggregates (
                asset_id, nsg_ref, year,
                total_jobs_raised,
                emergency_jobs_2hr, urgent_jobs_24hr, jobs_5day, jobs_28day,
                pothole_count, patching_count, edge_count, drainage_count, other_count,
                most_recent_defect_date, days_since_most_recent_defect,
                jobs_completed, jobs_outstanding,
                mean_days_to_completion, oldest_outstanding_days,
                rebuilt_at
            )
            SELECT
                asset_id,
                MIN(nsg_ref)                                                              AS nsg_ref,
                EXTRACT(YEAR FROM job_entry_date)::int                                   AS year,
                COUNT(*)                                                                  AS total_jobs_raised,
                COUNT(*) FILTER (WHERE priority_category = 1)                            AS emergency_jobs_2hr,
                COUNT(*) FILTER (WHERE priority_category = 2)                            AS urgent_jobs_24hr,
                COUNT(*) FILTER (WHERE priority_category = 3)                            AS jobs_5day,
                COUNT(*) FILTER (WHERE priority_category = 4)                            AS jobs_28day,
                COUNT(*) FILTER (WHERE job_type_category = 'pothole')                    AS pothole_count,
                COUNT(*) FILTER (WHERE job_type_category = 'patching')                   AS patching_count,
                COUNT(*) FILTER (WHERE job_type_category = 'edge')                       AS edge_count,
                COUNT(*) FILTER (WHERE job_type_category = 'drainage')                   AS drainage_count,
                COUNT(*) FILTER (WHERE job_type_category = 'other')                      AS other_count,
                MAX(job_entry_date)                                                       AS most_recent_defect_date,
                (CURRENT_DATE - MAX(job_entry_date)::date)                               AS days_since_most_recent_defect,
                COUNT(*) FILTER (WHERE actual_comp_date IS NOT NULL)                     AS jobs_completed,
                COUNT(*) FILTER (WHERE actual_comp_date IS NULL)                         AS jobs_outstanding,
                AVG(actual_comp_date::date - job_entry_date::date)
                    FILTER (WHERE actual_comp_date IS NOT NULL
                              AND actual_comp_date >= job_entry_date)                    AS mean_days_to_completion,
                (CURRENT_DATE - (MIN(job_entry_date) FILTER (WHERE actual_comp_date IS NULL))::date)
                                                                                          AS oldest_outstanding_days,
                NOW()                                                                     AS rebuilt_at
            FROM reactive_job_records
            WHERE asset_id = ANY(:ids)
              AND job_entry_date IS NOT NULL
            GROUP BY asset_id, EXTRACT(YEAR FROM job_entry_date)::int
        """), {"ids": asset_ids})

    agg_count = db.execute(
        _text("SELECT COUNT(*) FROM reactive_aggregates WHERE asset_id = ANY(:ids)"),
        {"ids": asset_ids},
    ).scalar() if asset_ids else 0
    aggregates_rebuilt = agg_count or 0

    db.commit()
    return ReactiveRawIngestionResult(
        jobs_ingested=jobs_ingested,
        jobs_skipped=jobs_skipped,
        jobs_filtered_out=filtered_out,
        assets_created=assets_created,
        aggregates_rebuilt=aggregates_rebuilt,
        years_found=sorted(years_found),
        job_type_breakdown=job_type_breakdown,
        validation=val_result.to_dict() if val_result else None,
    )


# ── Network master register ───────────────────────────────────────────────────

@router.post("/upload/network", response_model=NetworkIngestionResult)
async def upload_network(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_contributor),
):
    """
    Ingest the WSCC road network file (.gpkg or .zip containing .shp).
    Filters to ABCD classes + WSCC ownership, aggregates to one row per NSG,
    reprojects geometry to WGS84, upserts into network_assets.
    """
    content = await file.read()
    fname = file.filename or "network_upload"

    val_result = None
    try:
        val_df = await asyncio.get_event_loop().run_in_executor(
            None, read_network_for_validation, content, fname
        )
        if not val_df.empty:
            val_result = _validator.validate(val_df, NETWORK_SHP_SCHEMA)
            if not val_result.passed:
                raise HTTPException(status_code=422, detail=val_result.to_dict())
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Network validation read error: %s", exc)

    try:
        records = await asyncio.get_event_loop().run_in_executor(
            None, parse_network_file, content, fname
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Network parse error: %s", exc)
        raise HTTPException(status_code=400, detail=f"Failed to parse network file: {exc}")

    ingested = 0
    total_length = 0.0
    by_class: dict[str, float] = {}

    for rec in records:
        nsg = rec["nsg_ref"]
        existing = db.query(NetworkAsset).filter(
            NetworkAsset.authority_id == current_user.authority_id,
            NetworkAsset.nsg_ref == nsg,
        ).first()

        if existing:
            for k, v in rec.items():
                setattr(existing, k, v)
        else:
            db.add(NetworkAsset(authority_id=current_user.authority_id, **rec))

        ingested += 1
        total_length += rec.get("length_m") or 0.0
        cls = rec.get("road_class") or "?"
        by_class[cls] = by_class.get(cls, 0.0) + (rec.get("length_m") or 0.0)

    db.commit()

    # Coverage analysis — how many network NSGs have condition/reactive data
    from sqlalchemy import text as _text
    row = db.execute(_text("""
        SELECT
            COUNT(*)                                                                AS total_matched,
            COUNT(CASE WHEN EXISTS(
                SELECT 1 FROM scanner_raw_records s WHERE s.asset_id = a.id
            ) THEN 1 END)                                                           AS has_scanner,
            COUNT(CASE WHEN EXISTS(
                SELECT 1 FROM cvi_raw_records c WHERE c.asset_id = a.id
            ) THEN 1 END)                                                           AS has_cvi,
            COUNT(CASE WHEN EXISTS(
                SELECT 1 FROM scrim_records sc WHERE sc.asset_id = a.id
            ) THEN 1 END)                                                           AS has_scrim,
            COUNT(CASE WHEN EXISTS(
                SELECT 1 FROM reactive_aggregates r WHERE r.asset_id = a.id
            ) THEN 1 END)                                                           AS has_reactive
        FROM network_assets na
        JOIN assets a ON a.nsg_ref = na.nsg_ref
        WHERE na.authority_id = :auth_id
    """), {"auth_id": current_user.authority_id}).fetchone()

    total_matched = row[0] or 0
    has_any = max(row[1] or 0, row[2] or 0, row[3] or 0, row[4] or 0)
    coverage = {
        "total_network_nsgs": ingested,
        "nsgs_matched_to_assets": total_matched,
        "nsgs_with_scanner":  row[1] or 0,
        "nsgs_with_cvi":      row[2] or 0,
        "nsgs_with_scrim":    row[3] or 0,
        "nsgs_with_reactive": row[4] or 0,
        "nsgs_with_no_data":  total_matched - has_any,
    }

    return NetworkIngestionResult(
        nsgs_ingested=ingested,
        total_length_km=round(total_length / 1000, 2),
        by_class={k: round(v / 1000, 2) for k, v in sorted(by_class.items())},
        coverage_analysis=coverage,
        validation=val_result.to_dict() if val_result else None,
    )


@router.get("/map-data")
def map_data(
    road_class: Optional[str] = Query(None),
    risk_band: Optional[str] = Query(None),
    rci_band: Optional[str] = Query(None),
    authority_id: Optional[int] = Query(None, description="Admin only — filter by authority"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """GeoJSON FeatureCollection of all network NSGs with condition properties."""
    from sqlalchemy import text as _text
    from shapely import wkt as _wkt
    from shapely.geometry import mapping as _mapping
    import json

    auth_id = resolve_authority_id(current_user, authority_id)

    sql = _text("""
        WITH latest_score AS (
            SELECT DISTINCT ON (asset_id)
                asset_id, risk_band, composite_score, treatment_recommendation
            FROM risk_scores
            ORDER BY asset_id, scored_at DESC
        ),
        latest_scanner AS (
            SELECT DISTINCT ON (asset_id)
                asset_id, rci_band, avg_ci, red_pct
            FROM scanner_raw_records
            ORDER BY asset_id, survey_year DESC
        )
        SELECT
            na.nsg_ref,
            COALESCE(na.road_name,  a.road_name)  AS road_name,
            COALESCE(na.road_class, a.road_class) AS road_class,
            COALESCE(na.parish,     a.parish)     AS parish,
            na.geometry,
            ls.risk_band,
            ls.composite_score,
            ls.treatment_recommendation,
            lsc.rci_band,
            lsc.avg_ci,
            lsc.red_pct,
            (EXISTS(SELECT 1 FROM scanner_raw_records srr WHERE srr.asset_id = a.id)) AS has_scanner,
            (EXISTS(SELECT 1 FROM cvi_raw_records     crr WHERE crr.asset_id = a.id)) AS has_cvi,
            (EXISTS(SELECT 1 FROM scrim_records       scr WHERE scr.asset_id = a.id)) AS has_scrim,
            (EXISTS(SELECT 1 FROM reactive_aggregates rag WHERE rag.asset_id = a.id)) AS has_reactive
        FROM network_assets na
        LEFT JOIN assets a
            ON  a.nsg_ref      = na.nsg_ref
            AND (:auth_id IS NULL OR a.authority_id = :auth_id)
        LEFT JOIN latest_score  ls  ON ls.asset_id  = a.id
        LEFT JOIN latest_scanner lsc ON lsc.asset_id = a.id
        WHERE (:auth_id IS NULL OR na.authority_id = :auth_id)
          AND na.geometry IS NOT NULL
    """)

    rows = db.execute(sql, {"auth_id": auth_id}).fetchall()

    features = []
    for row in rows:
        if road_class and (row.road_class or "") != road_class:
            continue
        if risk_band and row.risk_band != risk_band:
            continue
        if rci_band and row.rci_band != rci_band:
            continue

        try:
            geom = _wkt.loads(row.geometry)
        except Exception:
            continue

        hs = bool(row.has_scanner)
        hc = bool(row.has_cvi)
        hsc = bool(row.has_scrim)
        hr = bool(row.has_reactive)

        features.append({
            "type": "Feature",
            "geometry": _mapping(geom),
            "properties": {
                "nsg_ref":                  row.nsg_ref,
                "road_name":                row.road_name,
                "road_class":               row.road_class,
                "parish":                   row.parish,
                "risk_band":                row.risk_band,
                "composite_score":          row.composite_score,
                "rci_band":                 row.rci_band,
                "avg_ci":                   row.avg_ci,
                "red_pct":                  row.red_pct,
                "treatment_recommendation": row.treatment_recommendation,
                "has_scanner":              hs,
                "has_cvi":                  hc,
                "has_scrim":                hsc,
                "has_reactive":             hr,
                "score_completeness":       round(sum([hs, hc, hsc, hr]) / 4 * 100),
            },
        })

    from fastapi.responses import Response as _Resp
    return _Resp(content=json.dumps({"type": "FeatureCollection", "features": features}),
                 media_type="application/json")


@router.get("/by-nsg/{nsg_ref}")
def get_by_nsg(
    nsg_ref: str,
    authority_id: Optional[int] = Query(None, description="Admin only — filter by authority"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return full scored asset detail for a single NSG reference."""
    auth_id = resolve_authority_id(current_user, authority_id)
    q = db.query(Asset).filter(Asset.nsg_ref == nsg_ref)
    if auth_id is not None:
        q = q.filter(Asset.authority_id == auth_id)
    asset = q.first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return _score_asset(asset, db)


@router.get("/network-stats")
def network_stats(
    authority_id: Optional[int] = Query(None, description="Admin only — filter by authority"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return network coverage summary for the dashboard."""
    from sqlalchemy import text as _text

    auth_id = resolve_authority_id(current_user, authority_id)

    q = db.query(NetworkAsset)
    if auth_id is not None:
        q = q.filter(NetworkAsset.authority_id == auth_id)
    count = q.count()

    if count == 0:
        return None

    # Length and class breakdown
    rows = db.execute(_text("""
        SELECT road_class, SUM(length_m) as total_m
        FROM network_assets
        WHERE (:auth_id IS NULL OR authority_id = :auth_id)
        GROUP BY road_class
        ORDER BY road_class
    """), {"auth_id": auth_id}).fetchall()

    total_m = sum(r[1] or 0 for r in rows)
    by_class = {r[0]: round((r[1] or 0) / 1000, 2) for r in rows if r[0]}

    # Coverage
    cov = db.execute(_text("""
        SELECT
            COUNT(*)                                                                AS total_matched,
            COUNT(CASE WHEN EXISTS(
                SELECT 1 FROM scanner_raw_records s WHERE s.asset_id = a.id
            ) THEN 1 END)                                                           AS has_scanner,
            COUNT(CASE WHEN EXISTS(
                SELECT 1 FROM cvi_raw_records c WHERE c.asset_id = a.id
            ) THEN 1 END)                                                           AS has_cvi,
            COUNT(CASE WHEN EXISTS(
                SELECT 1 FROM scrim_records sc WHERE sc.asset_id = a.id
            ) THEN 1 END)                                                           AS has_scrim,
            COUNT(CASE WHEN EXISTS(
                SELECT 1 FROM reactive_aggregates r WHERE r.asset_id = a.id
            ) THEN 1 END)                                                           AS has_reactive
        FROM network_assets na
        JOIN assets a ON a.nsg_ref = na.nsg_ref
        WHERE (:auth_id IS NULL OR na.authority_id = :auth_id)
    """), {"auth_id": auth_id}).fetchone()

    total_matched = cov[0] or 0

    return {
        "total_nsgs": count,
        "total_length_km": round(total_m / 1000, 2),
        "by_class": by_class,
        "nsgs_matched_to_assets": total_matched,
        "nsgs_with_scanner":  cov[1] or 0,
        "nsgs_with_cvi":      cov[2] or 0,
        "nsgs_with_scrim":    cov[3] or 0,
        "nsgs_with_reactive": cov[4] or 0,
        "nsgs_with_no_data":  total_matched - max(cov[1] or 0, cov[2] or 0, cov[3] or 0, cov[4] or 0),
    }


# ── Dataset inventory ─────────────────────────────────────────────────────────

def _dataset_agg(model, auth_id, db, *, year_col="survey_year", ts_col="ingested_at"):
    """Return {records, survey_years, last_updated} for one table. year_col=None skips years."""
    from sqlalchemy import func, distinct as _distinct
    ts_attr = getattr(model, ts_col)
    q = db.query(func.count(model.id), func.max(ts_attr))
    if auth_id is not None:
        q = q.filter(model.authority_id == auth_id)
    count, last_updated = q.one()
    years = []
    if year_col and count:
        year_attr = getattr(model, year_col)
        yq = db.query(_distinct(year_attr)).filter(year_attr.isnot(None))
        if auth_id is not None:
            yq = yq.filter(model.authority_id == auth_id)
        years = sorted(r[0] for r in yq.all())
    return {
        "records": count or 0,
        "survey_years": years,
        "last_updated": last_updated.isoformat() if last_updated else None,
    }


def _datasets_for_authority(auth_id, db):
    from sqlalchemy import func
    from models.vaisala import VaisalaSurvey

    scanner  = _dataset_agg(ScannerRawRecord, auth_id, db)
    cvi      = _dataset_agg(CviRawRecord, auth_id, db)
    scrim    = _dataset_agg(ScrimRecord, auth_id, db)
    reactive = _dataset_agg(ReactiveJobRecord, auth_id, db, year_col=None)
    if reactive["records"]:
        yq = db.query(ReactiveAggregate.year).distinct().filter(ReactiveAggregate.year.isnot(None))
        if auth_id is not None:
            yq = yq.filter(ReactiveAggregate.authority_id == auth_id)
        reactive["survey_years"] = sorted(r[0] for r in yq.all())

    net_q = db.query(func.count(NetworkAsset.id), func.max(NetworkAsset.ingested_at))
    if auth_id is not None:
        net_q = net_q.filter(NetworkAsset.authority_id == auth_id)
    net_count, net_ts = net_q.one()

    vq = db.query(
        func.count(VaisalaSurvey.id),
        func.coalesce(func.sum(VaisalaSurvey.section_count), 0),
        func.max(VaisalaSurvey.imported_at),
    )
    if auth_id is not None:
        vq = vq.filter(VaisalaSurvey.authority_id == auth_id)
    v_count, v_sections, v_ts = vq.one()

    return {
        "scanner":  scanner,
        "cvi":      cvi,
        "scrim":    scrim,
        "reactive": reactive,
        "network":  {
            "records":      net_count or 0,
            "last_updated": net_ts.isoformat() if net_ts else None,
        },
        "vaisala":  {
            "surveys":      v_count or 0,
            "sections":     int(v_sections or 0),
            "last_updated": v_ts.isoformat() if v_ts else None,
        },
    }


def _datasets_all_authorities(db):
    from models.user import Authority

    out = []
    for auth in db.query(Authority).order_by(Authority.name).all():
        datasets = _datasets_for_authority(auth.id, db)
        has_data = any([
            datasets["scanner"]["records"],
            datasets["cvi"]["records"],
            datasets["scrim"]["records"],
            datasets["reactive"]["records"],
            datasets["network"]["records"],
            datasets["vaisala"]["surveys"],
        ])
        if has_data:
            out.append({
                "authority_id":   auth.id,
                "authority_name": auth.name,
                "slug":           auth.slug,
                "datasets":       datasets,
            })
    return {"authorities": out, "total_authorities": len(out)}


@router.get("/my-datasets")
def my_datasets(
    authority_id: Optional[int] = Query(None, description="Admin only — filter by authority"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Dataset inventory.
    Non-admin: own authority flat summary.
    Admin + authority_id param: single authority flat summary.
    Admin, no param: all authorities grouped by authority.
    """
    auth_id = resolve_authority_id(current_user, authority_id)
    if current_user.role == "admin" and auth_id is None:
        return _datasets_all_authorities(db)
    return _datasets_for_authority(auth_id, db)
