import csv
import io

import pytest
from sqlalchemy.exc import IntegrityError

from test_evidence_reporting import api  # registers the JSONB SQLite compiler
from models.vaisala import VaisalaSection, VaisalaSurvey
from models.user import User
from models.vaisala_programme import VaisalaProgramme, VaisalaProgrammeItem, VaisalaProgrammeReviewEvent
from services.vaisala_scoring import RAG_VALIDATED_WEIGHTS


@pytest.fixture
def survey(api):
    _, _, sessions = api
    with sessions() as db:
        survey = VaisalaSurvey(authority_id=1, source_filename="programme.csv", source_format="csv", network_key="test")
        db.add(survey)
        db.flush()
        for index, score in enumerate([4, 4, 2, None, 0]):
            positive = index < 4
            proportions = {key: 0 for key in RAG_VALIDATED_WEIGHTS}
            proportions["Subsidence"] = 1 if positive else 0
            db.add(VaisalaSection(survey_id=survey.id, authority_id=1, section_ref=f"P{index}",
                road_name="Example road", length_m=100, priority_score=score,
                rag_band="Red" if score and score >= 4 else "Amber" if score else "Green",
                structural_pct=1 if positive else 0, alligator_pct=0, edge_pct=0,
                localised_pct=0, dressing_pct=0, micro_pct=0,
                defect_proportions=proportions, defect_evidence_complete=True,
                qc_completeness_pct=100, qc_reliability_pct=100))
        db.commit()
        return survey.id


def save(client, headers, survey, key="save-1", **changes):
    return client.post(f"/vaisala/surveys/{survey}/programmes", headers=headers["manager"],
                       json={"idempotency_key": key, **changes})


def test_preview_complete_ranks_filters_no_writes_or_provider(api, survey, monkeypatch):
    from services import llm
    monkeypatch.setattr(llm, "_get_client", lambda: pytest.fail("Programme must not use a provider"))
    client, headers, sessions = api
    path = f"/vaisala/surveys/{survey}/programme"
    response = client.get(path, headers=headers["viewer"])
    assert response.status_code == 200, response.text
    full = response.json()
    assert full["total"] == full["summary"]["total_items"] == 5
    assert sum(full["summary"]["action_counts"].values()) == 5
    by_ref = {item["section_ref"]: item for item in full["items"]}
    assert [by_ref[f"P{i}"]["queue_rank"] for i in range(4)] == [1, 1, 3, None]
    filtered = client.get(path, headers=headers["viewer"], params={"search": "P2", "page_size": 1}).json()
    assert filtered["total"] == 5 and filtered["filtered_total"] == 1
    assert filtered["summary"] == full["summary"]
    assert filtered["items"][0]["queue_rank"] == 3
    unknown = client.get(path, headers=headers["viewer"], params={"search": "P3"}).json()["items"][0]
    assert unknown["priority_score"] is None
    detail = client.get(path + "/items/" + unknown["item_key"], headers=headers["viewer"])
    assert detail.status_code == 200
    assert client.get(path + "/items/absent", headers=headers["viewer"]).status_code == 404
    assert client.get(path, headers=headers["viewer"], params={"merge_scale": "nonsense"}).status_code == 400
    assert client.get(path, headers=headers["viewer"], params={"merge_scale": "10m"}).status_code == 422
    assert client.get(path, headers=headers["viewer"], params={"page_size": 201}).status_code == 422
    with sessions() as db:
        assert db.query(VaisalaProgramme).count() == 0


def test_empty_survey_and_other_authority_scope(api, survey):
    client, headers, sessions = api
    with sessions() as db:
        other = VaisalaSurvey(authority_id=2, source_filename="other.csv", source_format="csv", network_key="other")
        db.add(other)
        db.commit()
        other_id = other.id
    path = f"/vaisala/surveys/{other_id}"
    assert client.get(path + "/programme", headers=headers["manager"]).status_code == 404
    assert client.get(path + "/programme/export", headers=headers["viewer"]).status_code == 404
    assert save(client, headers, other_id).status_code == 404
    empty = client.get(path + "/programme", headers=headers["admin"])
    assert empty.status_code == 200, empty.text
    assert empty.json()["summary"]["total_items"] == 0
    assert empty.json()["items"] == []


def test_snapshot_idempotency_frozen_source_and_audit_restriction(api, survey):
    client, headers, sessions = api
    response = save(client, headers, survey)
    assert response.status_code == 201, response.text
    snapshot = response.json()
    assert save(client, headers, survey).json()["id"] == snapshot["id"]
    assert save(client, headers, survey, split="urban").status_code == 409
    assert client.post(f"/vaisala/surveys/{survey}/programmes", headers=headers["viewer"],
                       json={"idempotency_key": "viewer"}).status_code == 403
    assert client.post(f"/vaisala/surveys/{survey}/programmes", headers=headers["manager"],
                       json={"idempotency_key": "forged", "items": []}).status_code == 422
    with sessions() as db:
        db.query(VaisalaSection).filter_by(survey_id=survey, section_ref="P0").first().priority_score = 99
        db.commit()
    path = f"/vaisala/surveys/{survey}/programmes/{snapshot['id']}"
    reread = client.get(path, headers=headers["viewer"]).json()
    assert reread["items"] == snapshot["items"]
    assert client.get(f"/vaisala/surveys/{survey}/programmes", headers=headers["viewer"]).json()[0]["id"] == snapshot["id"]
    regenerated = save(client, headers, survey, key="save-2").json()
    assert regenerated["id"] != snapshot["id"]
    with sessions() as db:
        assert db.query(VaisalaProgramme).count() == 2
        db.delete(db.get(VaisalaSurvey, survey))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_reviews_concurrency_permissions_reasons_and_frozen_model(api, survey):
    client, headers, sessions = api
    snapshot = save(client, headers, survey).json()
    item = snapshot["items"][0]
    path = f"/vaisala/programmes/{snapshot['id']}/items/{item['item_key']}/reviews"
    body = {"expected_sequence": 0, "status": "accepted", "client_action": "monitor", "comment": "Engineer checked imagery"}
    assert client.post(path, headers=headers["viewer"], json=body).status_code == 403
    assert client.post(path, headers=headers["manager"], json={**body, "comment": ""}).status_code == 422
    response = client.post(path, headers=headers["manager"], json=body)
    assert response.status_code == 201, response.text
    assert response.json()["sequence"] == 1
    assert client.post(path, headers=headers["manager"], json=body).status_code == 409
    for changes in ({"status": "assigned", "assignee": ""}, {"status": "deferred", "comment": ""}, {"status": "unreviewed"}):
        assert client.post(path, headers=headers["manager"], json={**body, "expected_sequence": 1, **changes}).status_code == 422
    assert client.post(path, headers=headers["manager"], json={**body, "expected_sequence": 1, "status": "assigned", "assignee": "Team A"}).status_code == 201
    detail_path = f"/vaisala/surveys/{survey}/programmes/{snapshot['id']}/items/{item['item_key']}"
    current = client.get(detail_path, headers=headers["viewer"]).json()
    assert current["recommended_action"] == item["recommended_action"]
    assert current["review"]["client_action"] == "monitor"
    assert current["effective_action"] == "monitor"
    monitor = client.get(f"/vaisala/surveys/{survey}/programmes/{snapshot['id']}",
                         headers=headers["viewer"], params={"action": "monitor"}).json()
    assert monitor["filtered_total"] == 1
    assert monitor["summary"]["current_action_counts"]["monitor"] == 1
    assert monitor["summary"]["action_counts"]["monitor"] == 0
    assert [event["sequence"] for event in current["review_history"]] == [1, 2]
    with sessions() as db:
        saved = db.query(VaisalaProgrammeItem).filter_by(programme_id=snapshot["id"], item_key=item["item_key"]).one()
        assert saved.assessment["recommended_action"] == item["recommended_action"]
        assert "review" not in saved.assessment
        assert db.query(VaisalaProgrammeReviewEvent).filter_by(item_id=saved.id).count() == 2


def test_policy_validation_pinning_and_authority_isolation(api, survey):
    client, headers, sessions = api
    path = f"/vaisala/surveys/{survey}/programme/policies"
    assert client.post(path, headers=headers["manager"], json={"version": "local-v1"}).status_code == 403
    for changes in ({"automatic_monitoring_enabled": "yes"}, {"red_threshold": 2}, {"qc_adequacy_pct": 84}, {"surface_threshold_pct": 101}, {"acceptable_minor_extent_pct": 6}):
        assert client.post(path, headers=headers["admin"], json={"version": "bad", **changes}).status_code == 422
    policy = client.post(path, headers=headers["admin"], json={"version": "local-v1", "surface_threshold_pct": 8})
    assert policy.status_code == 201, policy.text
    assert client.post(path, headers=headers["admin"], json={"version": "local-v1"}).status_code == 409
    snapshot = save(client, headers, survey, policy_version="local-v1").json()
    assert snapshot["policy_version"] == "local-v1"
    assert client.post(path, headers=headers["admin"], json={"version": "local-v2"}).status_code == 201
    assert client.get(path, headers=headers["viewer"]).json()["active_version"] == "local-v2"
    assert save(client, headers, survey, policy_version="local-v1").json()["id"] == snapshot["id"]
    with sessions() as db:
        other = VaisalaSurvey(authority_id=2, source_filename="other.csv", source_format="csv", network_key="other")
        db.add(other); db.commit(); other_id = other.id
    other_path = f"/vaisala/surveys/{other_id}/programme"
    assert client.get(other_path, headers=headers["admin"]).json()["policy_version"] == "vaisala-programme-default-v2"
    assert client.get(other_path, headers=headers["admin"], params={"policy_version": "local-v1"}).status_code == 404


def test_saved_exports_match_reviewed_snapshot_and_filters_are_explicit(api, survey):
    client, headers, _ = api
    snapshot = save(client, headers, survey).json()
    path = f"/vaisala/surveys/{survey}/programmes/{snapshot['id']}/export"
    response = client.get(path, headers=headers["viewer"], params={"format": "csv", "search": "no-such-road"})
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == snapshot["total"]
    assert {(r["item_key"], r["recommended_action"], r["queue_rank"]) for r in rows} == {
        (i["item_key"], i["recommended_action"], str(i["queue_rank"]) if i["queue_rank"] is not None else "") for i in snapshot["items"]}
    filtered = client.get(path, headers=headers["viewer"], params={"format": "csv", "filtered": True, "search": "P0"})
    rows = list(csv.DictReader(io.StringIO(filtered.content.decode("utf-8-sig"))))
    assert len(rows) == 1 and '"search": "P0"' in rows[0]["export_filters"]
    assert rows[0]["export_scope"] == "filtered"


def test_saved_programme_all_routes_hide_other_authority(api, survey):
    client, headers, sessions = api
    snapshot = save(client, headers, survey).json()
    item_key = snapshot["items"][0]["item_key"]
    with sessions() as db:
        db.query(User).filter(User.role.in_(["manager", "viewer"])).update({"authority_id": 2}, synchronize_session=False)
        db.commit()
    base = f"/vaisala/surveys/{survey}/programmes"
    for path in (base, f"{base}/{snapshot['id']}", f"{base}/{snapshot['id']}/items/{item_key}", f"{base}/{snapshot['id']}/export"):
        assert client.get(path, headers=headers["manager"]).status_code == 404
    review_path = f"/vaisala/programmes/{snapshot['id']}/items/{item_key}/reviews"
    assert client.post(review_path, headers=headers["manager"], json={"expected_sequence": 0, "status": "accepted"}).status_code == 404
    assert client.get(f"{base}/{snapshot['id']}", headers=headers["admin"]).status_code == 200
    with sessions() as db:
        assert db.query(VaisalaProgrammeReviewEvent).count() == 0


def test_migration020_upgrade_downgrade_preserves_existing_surveys(api, survey):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect
    from database import Base

    _, _, sessions = api
    path = Path(__file__).parents[1] / "alembic" / "versions" / "020_vaisala_programme.py"
    spec = importlib.util.spec_from_file_location("programme_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sessions.kw["bind"]
    audit_tables = [Base.metadata.tables[name] for name in (
        "vaisala_programme_review_events", "vaisala_programme_items", "vaisala_programmes", "vaisala_programme_policies")]
    # All operations target only this fixture's temporary SQLite database.
    for table in audit_tables:
        table.drop(engine)
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert "vaisala_programmes" in inspect(connection).get_table_names()
        migration.downgrade()
        assert "vaisala_programmes" not in inspect(connection).get_table_names()
        migration.upgrade()
    with sessions() as db:
        assert db.get(VaisalaSurvey, survey).source_filename == "programme.csv"
        assert db.query(VaisalaSection).filter_by(survey_id=survey).count() == 5
