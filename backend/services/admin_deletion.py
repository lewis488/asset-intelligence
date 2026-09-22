"""Authority-scoped inventory and deletion of retained uploads, never whole dataset types."""
from fastapi import HTTPException
from sqlalchemy import func, select

from models.user import Authority, User
from models.asset import (Asset, ScannerRecord, ScannerRawRecord, CviRecord, CviRawRecord,
                          ScrimRecord, ReactiveJob, ReactiveJobRecord, ReactiveAggregate,
                          NetworkAsset, RiskScore, AnalysisRun)
from models.vaisala import (VaisalaSurvey, VaisalaSection, VaisalaInterval, VaisalaRagDriftLog,
                            VaisalaNetworkGeometry, VaisalaNetworkFeature)
from services.reactive_aggregates import rebuild_reactive_aggregates

FILE_MODELS = {
    "scanner": (ScannerRecord, ScannerRawRecord),
    "cvi": (CviRecord, CviRawRecord),
    "scrim": (ScrimRecord,),
    "reactive": (ReactiveJob, ReactiveJobRecord),
    "network": (NetworkAsset,),
}


def authority_assets(authority_id):
    return select(Asset.id).where(Asset.authority_id == authority_id)


def file_scope(model, authority_id):
    return (model.authority_id == authority_id if model is NetworkAsset
            else model.asset_id.in_(authority_assets(authority_id)))


def uploaded_sources(db, authority_id):
    """Non-Vaisala imports have no batch IDs: group retained rows by exact source filename."""
    grouped = {}
    for dataset, models in FILE_MODELS.items():
        for model in models:
            rows = db.query(model.source_file, func.count(model.id), func.max(model.ingested_at)).filter(
                file_scope(model, authority_id)).group_by(model.source_file)
            for filename, count, uploaded_at in rows:
                item = grouped.setdefault((dataset, filename), dict(
                    dataset_type=dataset, source_file=filename, upload_id=None, record_count=0, uploaded_at=None))
                item["record_count"] += count
                if uploaded_at and (item["uploaded_at"] is None or uploaded_at > item["uploaded_at"]):
                    item["uploaded_at"] = uploaded_at
    result = list(grouped.values())
    intervals = select(func.count(VaisalaInterval.id)).where(VaisalaInterval.survey_id == VaisalaSurvey.id).scalar_subquery()
    sections = select(func.count(VaisalaSection.id)).where(VaisalaSection.survey_id == VaisalaSurvey.id).scalar_subquery()
    for survey, interval_count, section_count in db.query(VaisalaSurvey, intervals, sections).filter(VaisalaSurvey.authority_id == authority_id):
        result.append(dict(dataset_type="vaisala", source_file=survey.source_filename, upload_id=survey.id,
                           record_count=interval_count or section_count, uploaded_at=survey.imported_at))
    features = select(func.count(VaisalaNetworkFeature.id)).where(VaisalaNetworkFeature.geometry_id == VaisalaNetworkGeometry.id).scalar_subquery()
    for geometry, count in db.query(VaisalaNetworkGeometry, features).filter(VaisalaNetworkGeometry.authority_id == authority_id):
        result.append(dict(dataset_type="vaisala_network", source_file=geometry.source_filename, upload_id=geometry.id,
                           record_count=count, uploaded_at=geometry.created_at))
    return sorted(result, key=lambda row: (row["dataset_type"], row["source_file"] or "", row["upload_id"] or 0))


def delete_upload(db, authority_id, dataset, target):
    if dataset in FILE_MODELS:
        if target.model_fields_set != {"source_file"}:
            raise HTTPException(422, "Select one source file to delete")
        deleted = 0
        for model in FILE_MODELS[dataset]:
            deleted += db.query(model).filter(file_scope(model, authority_id), model.source_file == target.source_file).delete(synchronize_session=False)
        if not deleted:
            raise HTTPException(404, "Source file not found for this authority")
        if dataset == "reactive":
            rebuild_reactive_aggregates(db, authority_assets(authority_id))
    else:
        if target.model_fields_set != {"upload_id"} or target.upload_id is None:
            raise HTTPException(422, "Select one survey or geometry upload to delete")
        model = VaisalaSurvey if dataset == "vaisala" else VaisalaNetworkGeometry
        upload = db.query(model).filter(model.id == target.upload_id, model.authority_id == authority_id).with_for_update().first()
        if upload is None:
            raise HTTPException(404, "Upload not found for this authority")
        # Bulk deletion avoids loading potentially millions of interval/feature rows into memory.
        if dataset == "vaisala":
            for child in (VaisalaRagDriftLog, VaisalaInterval, VaisalaSection):
                db.query(child).filter(child.survey_id == upload.id).delete(synchronize_session=False)
        else:
            db.query(VaisalaNetworkFeature).filter(VaisalaNetworkFeature.geometry_id == upload.id).delete(synchronize_session=False)
        db.query(model).filter(model.id == upload.id).delete(synchronize_session=False)
    # Saved analysis must not continue presenting deleted source data as current.
    db.query(RiskScore).filter(RiskScore.asset_id.in_(authority_assets(authority_id))).delete(synchronize_session=False)
    db.query(AnalysisRun).filter(AnalysisRun.authority_id == authority_id).delete(synchronize_session=False)


def delete_empty_authority(db, authority_id):
    if db.query(User.id).filter(User.authority_id == authority_id).first():
        raise HTTPException(409, "Remove or reassign all users before deleting this authority")
    for models in FILE_MODELS.values():
        for model in models:
            if db.query(model.id).filter(file_scope(model, authority_id)).first():
                raise HTTPException(409, "Delete all surveys and source files before deleting this authority")
    for model in (VaisalaSurvey, VaisalaNetworkGeometry):
        if db.query(model.id).filter(model.authority_id == authority_id).first():
            raise HTTPException(409, "Delete all surveys and geometry uploads before deleting this authority")
    ids = authority_assets(authority_id)
    if db.query(VaisalaSection.id).filter(VaisalaSection.asset_id.in_(ids)).first():
        raise HTTPException(409, "Survey records still reference this authority's assets")
    # Once all source data is gone, remove only the remaining derived rows and asset shells.
    for model in (RiskScore, ReactiveAggregate):
        db.query(model).filter(model.asset_id.in_(ids)).delete(synchronize_session=False)
    db.query(AnalysisRun).filter(AnalysisRun.authority_id == authority_id).delete(synchronize_session=False)
    db.query(Asset).filter(Asset.authority_id == authority_id).delete(synchronize_session=False)
    db.query(Authority).filter(Authority.id == authority_id).delete(synchronize_session=False)
