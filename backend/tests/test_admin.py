import os
from datetime import datetime

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_permissions.db")
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from main import app
from models.user import Authority, User
from models.asset import Asset, ScannerRecord, ScannerRawRecord, NetworkAsset
from models.vaisala import VaisalaSurvey, VaisalaSection, VaisalaInterval
from services.auth import hash_password


@pytest.fixture
def api(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'admin.db'}")
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add_all([Authority(id=1, name="First"), Authority(id=2, name="Empty")])
        db.flush()
        for role in ("admin", "manager", "viewer"):
            db.add(User(email=f"{role}@example.com", authority_id=1, role=role,
                        hashed_password=hash_password("test-password")))
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        headers = {}
        for role in ("admin", "manager", "viewer"):
            response = client.post("/auth/login", data={"username": f"{role}@example.com", "password": "test-password"})
            assert response.status_code == 200
            headers[role] = {"Authorization": "Bearer " + response.json()["access_token"]}
        yield client, headers, sessions
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.mark.parametrize("role", ["manager", "viewer"])
@pytest.mark.parametrize("method,path,payload", [
    ("GET", "/admin/users", None), ("GET", "/admin/authorities", None),
    ("GET", "/admin/data-overview", None),
    ("POST", "/admin/authorities", {"name": "New", "region": "South"}),
    ("PATCH", "/admin/authorities/1", {"name": "Changed"}),
    ("POST", "/admin/users", {"email": "new@example.com", "password": "test-password", "role": "admin", "authority_id": 1}),
    ("PATCH", "/admin/users/1", {"role": "viewer"}),
])
def test_non_admin_cannot_call_admin_api(api, role, method, path, payload):
    client, headers, _ = api
    assert client.request(method, path, headers=headers[role], json=payload).status_code == 403


def test_admin_management_and_deactivation(api):
    client, headers, sessions = api
    auth = headers["admin"]
    created = client.post("/admin/authorities", headers=auth, json={"name": "New", "region": "South"})
    assert created.status_code == 201
    authority_id = created.json()["id"]
    renamed = client.patch(f"/admin/authorities/{authority_id}", headers=auth, json={"name": "Renamed"})
    assert renamed.json()["name"] == "Renamed"
    assert renamed.json()["region"] == "South"
    assert len(client.get("/admin/authorities", headers=auth).json()) == 3
    payload = {"email": "new@example.com", "password": "test-password", "authority_id": authority_id, "role": "manager"}
    created = client.post("/admin/users", headers=auth, json=payload)
    assert created.status_code == 201
    user_id = created.json()["id"]
    assert created.json()["is_active"] is True
    assert "password" not in created.text
    login = client.post("/auth/login", data={"username": payload["email"], "password": payload["password"]})
    old_token = {"Authorization": "Bearer " + login.json()["access_token"]}
    changed = client.patch(f"/admin/users/{user_id}", headers=auth, json={"role": "viewer", "authority_id": 2, "is_active": False})
    assert changed.status_code == 200
    assert changed.json()["authority_id"] == 2
    assert changed.json()["role"] == "viewer"
    assert changed.json()["is_active"] is False
    assert client.get("/assets/", headers=old_token).status_code == 401
    assert client.post("/auth/login", data={"username": payload["email"], "password": payload["password"]}).status_code == 401
    users = client.get("/admin/users", headers=auth).json()
    assert len(users) == 4 and "hashed_password" not in str(users)
    with sessions() as db:
        assert db.get(User, user_id).hashed_password != payload["password"]


def test_validation_and_public_registration(api):
    client, headers, _ = api
    auth = headers["admin"]
    payload = {"email": "new@example.com", "password": "test-password", "authority_id": 999, "role": "viewer"}
    assert client.post("/admin/users", headers=auth, json=payload).status_code == 404
    payload.update(authority_id=1, email="admin@example.com")
    assert client.post("/admin/users", headers=auth, json=payload).status_code == 409
    for patch in ({"role": "owner"}, {"role": None}, {"authority_id": None}, {"is_active": None}, {}):
        assert client.patch("/admin/users/2", headers=auth, json=patch).status_code == 422
    assert client.patch("/admin/users/999", headers=auth, json={"role": "viewer"}).status_code == 404
    assert client.post("/admin/authorities", headers=auth, json={"name": "  "}).status_code == 422
    assert client.get("/admin/users").status_code == 401
    assert client.post("/auth/register", json={"email": "public@example.com", "password": "test-password", "authority_name": "Public", "role": "admin"}).status_code == 403


def test_overview_counts_legacy_raw_and_empty_authorities(api):
    client, headers, sessions = api
    with sessions() as db:
        asset = Asset(authority_id=1, nsg_ref="1")
        db.add(asset)
        db.flush()
        db.add(ScannerRecord(asset_id=asset.id, ingested_at=datetime(2026, 1, 1)))
        db.add(ScannerRawRecord(asset_id=asset.id, authority_id=1, ingested_at=datetime(2026, 2, 1)))
        db.add(NetworkAsset(authority_id=2, nsg_ref="2", ingested_at=datetime(2026, 3, 1)))
        db.commit()
    response = client.get("/admin/data-overview", headers=headers["admin"])
    assert response.status_code == 200
    rows = {row["authority_id"]: row for row in response.json()["authorities"]}
    assert rows[1]["datasets"]["scanner"] == {"record_count": 2, "last_upload_date": "2026-02-01T00:00:00"}
    assert rows[2]["datasets"]["scanner"] == {"record_count": 0, "last_upload_date": None}
    assert rows[2]["datasets"]["network"]["record_count"] == 1


def test_overview_counts_shp_sections_without_double_counting_intervals(api):
    client, headers, sessions = api
    with sessions() as db:
        shp = VaisalaSurvey(authority_id=1, source_filename="test.shp", source_format="shp", network_key="test", imported_at=datetime(2026, 4, 1))
        raw = VaisalaSurvey(authority_id=1, source_filename="test.xlsx", source_format="xlsx", network_key="test", imported_at=datetime(2026, 5, 1))
        db.add_all([shp, raw])
        db.flush()
        db.add_all([VaisalaSection(survey_id=shp.id, section_ref="1", length_m=10),
                    VaisalaSection(survey_id=raw.id, section_ref="2", length_m=20),
                    VaisalaInterval(survey_id=raw.id, section_ref="2", length_m=10),
                    VaisalaInterval(survey_id=raw.id, section_ref="2", length_m=10)])
        db.commit()
    rows = client.get("/admin/data-overview", headers=headers["admin"]).json()["authorities"]
    first = next(row for row in rows if row["authority_id"] == 1)
    assert first["datasets"]["vaisala"] == {"record_count": 3, "last_upload_date": "2026-05-01T00:00:00"}
