"""Authority-scoped deterministic programmes, immutable snapshots and review audit."""
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from models.vaisala_programme import (
    VaisalaProgramme, VaisalaProgrammeItem, VaisalaProgrammePolicy, VaisalaProgrammeReviewEvent,
)
from routers.auth import get_current_user, require_admin, require_contributor
from routers.vaisala import _build_view_rows, _get_survey, _validate_view_params
from schemas.vaisala_programme import Action, ProgrammeItem, ProgrammePolicy, ProgrammeResponse, ReviewInput, SaveProgramme
from services.vaisala_programme import ACTIONS, DEFAULT_POLICY, _coverage, build_programme, validate_policy
from services.vaisala_programme_exports import export_programme

router = APIRouter(prefix="/vaisala", tags=["vaisala-programme"])


def _survey(db, survey_id, user):
    survey = _get_survey(db, survey_id, user)
    if survey is None:
        raise HTTPException(404, "Survey not found")
    return survey


def _policy(db, authority_id, version=None):
    if version == DEFAULT_POLICY["version"]:
        return dict(DEFAULT_POLICY)
    query = db.query(VaisalaProgrammePolicy).filter_by(authority_id=authority_id)
    if version:
        record = query.filter_by(version=version).first()
        if record is None:
            raise HTTPException(404, "Policy version not found for this authority")
    else:
        record = query.order_by(VaisalaProgrammePolicy.id.desc()).first()
    return validate_policy(record.policy if record else DEFAULT_POLICY)


def _unreviewed():
    return {"sequence": 0, "status": "unreviewed", "client_action": None,
            "comment": "", "assignee": "", "reviewer_id": None, "reviewer_name": None, "created_at": None}


def _preview(db, survey, merge_scale, split, policy_version):
    _validate_view_params(merge_scale, split, "defect")
    policy = _policy(db, survey.authority_id, policy_version)
    rows = _build_view_rows(db, survey.id, merge_scale, split, include_unknown=True, assess=False)
    payload = build_programme(rows, survey_id=survey.id, policy=policy)
    payload.update({"generated_at": datetime.now(timezone.utc).isoformat(),
                    "merge_scale": merge_scale, "split": split, "policy": policy,
                    "source_filename": survey.source_filename,
                    "imported_at": survey.imported_at.isoformat() if survey.imported_at else None})
    for item in payload["items"]:
        item["review"] = _unreviewed()
    _current_actions(payload)
    return payload


def _current_actions(payload):
    """Review routing is separate from frozen model ranks and decisions."""
    grouped = {action: [] for action in ACTIONS}
    for item in payload["items"]:
        item["effective_action"] = item.get("review", {}).get("client_action") or item["recommended_action"]
        item["client_action_overridden"] = item["effective_action"] != item["recommended_action"]
        grouped[item["effective_action"]].append(item)
    payload["summary"] = {**payload["summary"],
        "current_action_counts": {action: len(items) for action, items in grouped.items()},
        "current_action_lengths_m": {action: _coverage(items)[0] for action, items in grouped.items()}}


def filters(
    action: Action | None = None, search: str = Query("", max_length=200),
    scale: Literal["section", "100m", "10m"] | None = None,
    rag_band: Literal["Red", "Amber", "Green"] | None = None,
    evidence_status: Literal["adequate", "limited", "conflicting"] | None = None,
    review_status: Literal["unreviewed", "accepted", "assigned", "completed", "deferred"] | None = None,
):
    return {key: value for key, value in locals().items() if value not in (None, "")}


def _filter_items(items, selected):
    result = []
    for item in items:
        if selected.get("action") and item.get("effective_action", item["recommended_action"]) != selected["action"]:
            continue
        if selected.get("scale") and item.get("assessment_scope") != selected["scale"]:
            continue
        if selected.get("rag_band") and item.get("rag_band") != selected["rag_band"]:
            continue
        if selected.get("evidence_status") and item.get("evidence_status") != selected["evidence_status"]:
            continue
        if selected.get("review_status") and item.get("review", {}).get("status", "unreviewed") != selected["review_status"]:
            continue
        if selected.get("search"):
            haystack = " ".join(str(item.get(k) or "") for k in ("section_ref", "road_name", "net_reference", "item_key"))
            if selected["search"].casefold() not in haystack.casefold():
                continue
        result.append(item)
    return result


def _page(payload, selected, page, page_size):
    items = _filter_items(payload["items"], selected)
    return {**payload, "total": len(payload["items"]), "filtered_total": len(items),
            "page": page, "page_size": page_size, "filters": selected,
            "items": items[(page - 1) * page_size:page * page_size]}


def _get_snapshot(db, survey_id, programme_id, user):
    survey = _survey(db, survey_id, user)
    snapshot = db.query(VaisalaProgramme).filter_by(id=programme_id, survey_id=survey.id,
                                                   authority_id=survey.authority_id).first()
    if snapshot is None:
        raise HTTPException(404, "Programme not found")
    return snapshot


def _review_out(event):
    return {**event.decision, "sequence": event.sequence, "reviewer_id": event.author_id,
            "created_at": event.created_at.isoformat() if event.created_at else None}


def _snapshot_payload(db, snapshot):
    records = db.query(VaisalaProgrammeItem).filter_by(programme_id=snapshot.id).order_by(VaisalaProgrammeItem.id).all()
    # One joined query for the complete audit, never one query per programme item.
    events = (db.query(VaisalaProgrammeReviewEvent).join(VaisalaProgrammeItem)
              .filter(VaisalaProgrammeItem.programme_id == snapshot.id)
              .order_by(VaisalaProgrammeReviewEvent.sequence).all())
    histories = {}
    for event in events:
        histories.setdefault(event.item_id, []).append(_review_out(event))
    items = []
    for record in records:
        history = histories.get(record.id, [])
        items.append({**record.assessment, "review": history[-1] if history else _unreviewed(), "review_history": history})
    payload = {**snapshot.metadata_json, "id": snapshot.id, "items": items}
    _current_actions(payload)
    return payload


def _download(payload, format, selected, filtered):
    if filtered:
        payload = {**payload, "items": _filter_items(payload["items"], selected),
                   "export_filters": {"filtered": True, **selected}}
    content = export_programme(payload, format=format)
    media = "text/csv; charset=utf-8" if format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    filename = f"vaisala-programme-{payload.get('id') or 'preview'}-survey-{payload['survey_id']}.{format}"
    return StreamingResponse(io.BytesIO(content), media_type=media,
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/surveys/{survey_id}/programme", response_model=ProgrammeResponse)
def preview_programme(survey_id: int, merge_scale: str = "section", split: str = "combined",
                      policy_version: str | None = None, page: int = Query(1, ge=1),
                      page_size: int = Query(50, ge=1, le=200), selected: dict = Depends(filters),
                      db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    survey = _survey(db, survey_id, user)
    return _page(_preview(db, survey, merge_scale, split, policy_version), selected, page, page_size)


@router.get("/surveys/{survey_id}/programme/export")
def export_preview(survey_id: int, format: Literal["csv", "xlsx"] = "xlsx", filtered: bool = False,
                   merge_scale: str = "section", split: str = "combined", policy_version: str | None = None,
                   selected: dict = Depends(filters), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    survey = _survey(db, survey_id, user)
    return _download(_preview(db, survey, merge_scale, split, policy_version), format, selected, filtered)


@router.get("/surveys/{survey_id}/programme/items/{item_key}", response_model=ProgrammeItem)
def preview_item(survey_id: int, item_key: str, merge_scale: str = "section", split: str = "combined",
                 policy_version: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    survey = _survey(db, survey_id, user)
    payload = _preview(db, survey, merge_scale, split, policy_version)
    item = next((item for item in payload["items"] if item["item_key"] == item_key), None)
    if item is None:
        raise HTTPException(404, "Item not found in this programme view")
    return item


@router.get("/surveys/{survey_id}/programme/policies")
def list_policies(survey_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    survey = _survey(db, survey_id, user)
    records = db.query(VaisalaProgrammePolicy).filter_by(authority_id=survey.authority_id).order_by(VaisalaProgrammePolicy.id.desc()).all()
    return {"active_version": records[0].version if records else DEFAULT_POLICY["version"],
            "policies": [record.policy for record in records] + [dict(DEFAULT_POLICY)]}


@router.post("/surveys/{survey_id}/programme/policies", status_code=201)
def create_policy(survey_id: int, body: ProgrammePolicy, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    survey = _survey(db, survey_id, user)
    policy = validate_policy(body.model_dump())
    if policy["version"] == DEFAULT_POLICY["version"]:
        raise HTTPException(409, "The default policy version is immutable")
    record = VaisalaProgrammePolicy(authority_id=survey.authority_id, version=policy["version"], policy=policy, created_by=user.id)
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Policy version already exists for this authority")
    return policy


@router.post("/surveys/{survey_id}/programmes", response_model=ProgrammeResponse, status_code=201)
def save_programme(survey_id: int, body: SaveProgramme, db: Session = Depends(get_db), user: User = Depends(require_contributor)):
    survey = _survey(db, survey_id, user)
    request = {"survey_id": survey.id, **body.model_dump(exclude={"idempotency_key"})}
    fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()

    def existing():
        record = db.query(VaisalaProgramme).filter_by(authority_id=survey.authority_id, created_by=user.id,
                                                     idempotency_key=body.idempotency_key).first()
        if record and record.request_fingerprint != fingerprint:
            raise HTTPException(409, "Idempotency key was used for a different programme request")
        return record

    snapshot = existing()
    if snapshot:
        return _page(_snapshot_payload(db, snapshot), {}, 1, 50)
    payload = _preview(db, survey, body.merge_scale, body.split, body.policy_version)
    metadata = jsonable_encoder({k: v for k, v in payload.items() if k != "items"})
    snapshot = VaisalaProgramme(authority_id=survey.authority_id, survey_id=survey.id, created_by=user.id,
        idempotency_key=body.idempotency_key, request_fingerprint=fingerprint,
        model_version=payload["model_version"], policy_version=payload["policy_version"],
        merge_scale=body.merge_scale, split=body.split,
        generated_at=datetime.fromisoformat(payload["generated_at"]), metadata_json=metadata)
    try:
        db.add(snapshot)
        db.flush()
        # Batch insertion avoids retaining an ORM object for every source interval.
        batch = []
        for item in payload["items"]:
            batch.append({"programme_id": snapshot.id, "item_key": item["item_key"],
                          "assessment": jsonable_encoder({k: v for k, v in item.items() if k not in ("review", "review_history")})})
            if len(batch) == 1000:
                db.bulk_insert_mappings(VaisalaProgrammeItem, batch)
                batch = []
        if batch:
            db.bulk_insert_mappings(VaisalaProgrammeItem, batch)
        db.commit()
    except IntegrityError:
        db.rollback()
        snapshot = existing()
        if snapshot is None:
            raise HTTPException(409, "Programme could not be saved atomically; refresh and retry")
    return _page(_snapshot_payload(db, snapshot), {}, 1, 50)


@router.get("/surveys/{survey_id}/programmes")
def list_programmes(survey_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    survey = _survey(db, survey_id, user)
    records = db.query(VaisalaProgramme).filter_by(survey_id=survey.id, authority_id=survey.authority_id).order_by(VaisalaProgramme.id.desc()).all()
    return [{**record.metadata_json, "id": record.id} for record in records]


@router.get("/surveys/{survey_id}/programmes/{programme_id}", response_model=ProgrammeResponse)
def read_programme(survey_id: int, programme_id: int, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
                   selected: dict = Depends(filters), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    snapshot = _get_snapshot(db, survey_id, programme_id, user)
    return _page(_snapshot_payload(db, snapshot), selected, page, page_size)


@router.get("/surveys/{survey_id}/programmes/{programme_id}/items/{item_key}", response_model=ProgrammeItem)
def read_saved_item(survey_id: int, programme_id: int, item_key: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    snapshot = _get_snapshot(db, survey_id, programme_id, user)
    payload = _snapshot_payload(db, snapshot)
    item = next((item for item in payload["items"] if item["item_key"] == item_key), None)
    if item is None:
        raise HTTPException(404, "Item not found in saved programme")
    return item


@router.get("/surveys/{survey_id}/programmes/{programme_id}/export")
def export_saved(survey_id: int, programme_id: int, format: Literal["csv", "xlsx"] = "xlsx", filtered: bool = False,
                 selected: dict = Depends(filters), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    snapshot = _get_snapshot(db, survey_id, programme_id, user)
    return _download(_snapshot_payload(db, snapshot), format, selected, filtered)


@router.post("/programmes/{programme_id}/items/{item_key}/reviews", status_code=201)
def append_review(programme_id: int, item_key: str, body: ReviewInput,
                  db: Session = Depends(get_db), user: User = Depends(require_contributor)):
    query = db.query(VaisalaProgramme).filter_by(id=programme_id)
    if user.role != "admin":
        query = query.filter_by(authority_id=user.authority_id)
    snapshot = query.first()
    if snapshot is None:
        raise HTTPException(404, "Programme not found")
    _survey(db, snapshot.survey_id, user)
    item = (db.query(VaisalaProgrammeItem).filter_by(programme_id=snapshot.id, item_key=item_key)
            .with_for_update().first())
    if item is None:
        raise HTTPException(404, "Item not found in saved programme")
    previous = (db.query(VaisalaProgrammeReviewEvent).filter_by(item_id=item.id)
                .order_by(VaisalaProgrammeReviewEvent.sequence.desc()).first())
    sequence = previous.sequence if previous else 0
    if sequence != body.expected_sequence:
        raise HTTPException(409, "Review changed; refresh the item before saving your decision")
    old_action = previous.decision.get("client_action") if previous else None
    if body.client_action != old_action and not body.comment:
        raise HTTPException(422, "A reason is required when changing or clearing the client action")
    if body.status == "unreviewed" and sequence:
        raise HTTPException(422, "A reviewed item cannot return to unreviewed; record a new decision")
    decision = body.model_dump(exclude={"expected_sequence"})
    decision["reviewer_name"] = user.email
    event = VaisalaProgrammeReviewEvent(item_id=item.id, sequence=sequence + 1, author_id=user.id, decision=decision)
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Review changed; refresh the item before saving your decision")
    db.refresh(event)
    return _review_out(event)
