import os

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_permissions.db")
os.environ.setdefault("JWT_SECRET", "test-secret")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from main import app
from models.asset import Asset
from models.user import Authority, User
from services.auth import create_access_token, hash_password


def test_viewer_upload_is_forbidden_but_own_assets_are_readable(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'permissions.db'}")
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    db = Session()
    authority = Authority(name="Viewer Test Authority")
    db.add(authority)
    db.flush()
    viewer = User(
        authority_id=authority.id,
        email="viewer-test@roadiq.invalid",
        hashed_password=hash_password("viewer-test-password"),
        role="viewer",
    )
    db.add(viewer)
    db.add(Asset(authority_id=authority.id, nsg_ref="TEST-NSG-1", road_name="Viewer Road"))
    db.commit()

    token = create_access_token({"sub": str(viewer.id), "authority_id": authority.id})

    def override_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    try:
        upload = client.post(
            "/assets/upload/scanner",
            headers=headers,
            files={"file": ("scanner.csv", b"NSG,CI\nTEST-NSG-1,1\n", "text/csv")},
        )
        assets = client.get("/assets/", headers=headers)
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(engine)

    assert upload.status_code == 403
    assert assets.status_code == 200
    assert assets.json()["total"] == 1
    assert assets.json()["assets"][0]["nsg_ref"] == "TEST-NSG-1"
