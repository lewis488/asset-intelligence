"""Stored dataset counts, grouped in SQL by their owning authority.

Legacy and Confirm records are counted as stored rows, not unique roads.
Derived reactive aggregates and interval-derived Vaisala sections are excluded
to avoid counting the same source measurements twice. Dates are ingestion timestamps
on retained data; this is not a historical upload audit log.
"""
from sqlalchemy import func
from models.user import Authority
from models.asset import (Asset, ScannerRecord, ScannerRawRecord, CviRecord,
                          CviRawRecord, ScrimRecord, ReactiveJob, ReactiveJobRecord, NetworkAsset)
from models.vaisala import (VaisalaSurvey, VaisalaInterval, VaisalaSection,
                            VaisalaNetworkGeometry, VaisalaNetworkFeature)


def data_overview(db):
    keys = ("scanner", "cvi", "scrim", "reactive", "network", "vaisala", "vaisala_network")
    rows = {
        authority.id: {"authority_id": authority.id, "authority_name": authority.name,
                       "datasets": {key: {"record_count": 0, "last_upload_date": None} for key in keys}}
        for authority in db.query(Authority).order_by(Authority.name, Authority.id)
    }

    def accumulate(key, query):
        for authority_id, count, last_upload in query:
            if authority_id not in rows:
                continue
            dataset = rows[authority_id]["datasets"][key]
            dataset["record_count"] += count
            if last_upload is not None and (dataset["last_upload_date"] is None or last_upload > dataset["last_upload_date"]):
                dataset["last_upload_date"] = last_upload

    for key, model in (("scanner", ScannerRecord), ("scanner", ScannerRawRecord),
                       ("cvi", CviRecord), ("cvi", CviRawRecord), ("scrim", ScrimRecord),
                       ("reactive", ReactiveJob), ("reactive", ReactiveJobRecord)):
        # The asset FK also scopes legacy records whose authority_id was never populated.
        query = db.query(Asset.authority_id, func.count(model.id), func.max(model.ingested_at))
        query = query.select_from(model).join(Asset, model.asset_id == Asset.id).group_by(Asset.authority_id)
        accumulate(key, query)
    accumulate("network", db.query(NetworkAsset.authority_id, func.count(NetworkAsset.id),
                                    func.max(NetworkAsset.ingested_at)).group_by(NetworkAsset.authority_id))
    accumulate("vaisala", db.query(VaisalaSurvey.authority_id, func.count(VaisalaInterval.id),
                                    func.max(VaisalaSurvey.imported_at)).select_from(VaisalaSurvey)
               .outerjoin(VaisalaInterval, VaisalaInterval.survey_id == VaisalaSurvey.id)
               .group_by(VaisalaSurvey.authority_id))
    # SHP surveys have sections only. Count those only when no intervals exist.
    has_intervals = db.query(VaisalaInterval.id).filter(VaisalaInterval.survey_id == VaisalaSurvey.id).exists()
    accumulate("vaisala", db.query(VaisalaSurvey.authority_id, func.count(VaisalaSection.id),
                                    func.max(VaisalaSurvey.imported_at)).select_from(VaisalaSurvey)
               .join(VaisalaSection, VaisalaSection.survey_id == VaisalaSurvey.id)
               .filter(~has_intervals).group_by(VaisalaSurvey.authority_id))
    accumulate("vaisala_network", db.query(VaisalaNetworkGeometry.authority_id, func.count(VaisalaNetworkFeature.id),
                                            func.max(VaisalaNetworkGeometry.created_at)).select_from(VaisalaNetworkGeometry)
               .outerjoin(VaisalaNetworkFeature, VaisalaNetworkFeature.geometry_id == VaisalaNetworkGeometry.id)
               .group_by(VaisalaNetworkGeometry.authority_id))
    return {"authorities": list(rows.values()), "total_authorities": len(rows)}
