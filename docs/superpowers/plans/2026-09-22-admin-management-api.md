# Admin Management API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an admin-only API for authority, user, and cross-authority dataset management, with inactive-user enforcement.

**Architecture:** A new `routers/admin.py` owns privileged routes and uses an auth-layer `require_admin` dependency. Pydantic schemas define the public contract; a reversible Alembic migration introduces `users.is_active`; pytest proves authorization and response behaviour.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, pytest.

**Spec:** `docs/superpowers/specs/2026-09-22-admin-management-api-design.md`

## Global Constraints

- Every `/admin` endpoint returns 403 for manager and viewer tokens.
- Authority data remains scoped; only `require_admin` routes read across authorities.
- `users.is_active` defaults to true, preserves access on upgrade, and has a downgrade.
- Commit migrations `012`–`014` with `016`, because `015` depends on them.
- No frontend code is part of this change.

---

### Task 1: Authentication activation gate and migration

**Files:**
- Modify: `backend/models/user.py`
- Modify: `backend/routers/auth.py`
- Create: `backend/alembic/versions/016_users_is_active.py`
- Create: `backend/tests/test_admin.py`

**Interfaces:**
- Produces: `require_admin()` and `User.is_active: bool`.

- [ ] **Step 1: Write failing access tests**

```python
def test_manager_cannot_get_admin_users(client, manager_token):
    response = client.get("/admin/users", headers={"Authorization": f"Bearer {manager_token}"})
    assert response.status_code == 403

def test_inactive_user_token_is_rejected(client, inactive_user_token):
    response = client.get("/admin/users", headers={"Authorization": f"Bearer {inactive_user_token}"})
    assert response.status_code == 401
```

- [ ] **Step 2: Verify RED**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_admin.py -q`

Expected: FAIL because the admin route and activation gate do not exist.

- [ ] **Step 3: Implement the minimum activation gate**

```python
def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
```

Add `is_active = Column(Boolean, nullable=False, server_default="true", default=True)` to `User`. Add an inactive-user 401 after user lookup. Create `016_users_is_active` with `down_revision = "015_role_three_tier"`; upgrade adds a non-null server-defaulted true boolean and downgrade drops it.

- [ ] **Step 4: Verify GREEN after Task 2 registers the router**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_admin.py -q`

Expected: PASS for authorization and inactive-token cases.

### Task 2: Authority and user administration routes

**Files:**
- Create: `backend/schemas/admin.py`
- Create: `backend/routers/admin.py`
- Modify: `backend/main.py`
- Modify: `backend/tests/test_admin.py`

**Interfaces:**
- Consumes: `require_admin`, `Authority`, `User`, and password hashing.
- Produces: `/admin/authorities` and `/admin/users` endpoints.

- [ ] **Step 1: Write failing management tests**

```python
def test_admin_can_create_and_patch_authority(client, admin_headers):
    created = client.post("/admin/authorities", json={"name": "Test Council", "region": "South"}, headers=admin_headers)
    assert created.status_code == 201
    updated = client.patch(f"/admin/authorities/{created.json()['id']}", json={"region": "North"}, headers=admin_headers)
    assert updated.json()["region"] == "North"

def test_admin_can_create_and_update_user(client, admin_headers, authority_id):
    created = client.post("/admin/users", json={"email": "new@example.com", "password": "safe-password", "authority_id": authority_id, "role": "viewer"}, headers=admin_headers)
    assert created.status_code == 201
    assert created.json()["is_active"] is True
    updated = client.patch(f"/admin/users/{created.json()['id']}", json={"role": "manager", "is_active": False}, headers=admin_headers)
    assert updated.json()["role"] == "manager"
    assert updated.json()["is_active"] is False
```

- [ ] **Step 2: Verify RED**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_admin.py -q`

Expected: FAIL with 404 for `/admin/authorities` and `/admin/users` writes.

- [ ] **Step 3: Implement schemas and routes**

```python
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

@router.post("/users", response_model=AdminUserOut, status_code=201)
def create_user(req: AdminUserCreate, db: Session = Depends(get_db)):
    # reject duplicate email and unknown authority, hash password, persist and return user
```

Use strict role literals, email validation, an at-least-one-field patch model, `is_active` in user responses, duplicate name/email 409 responses, and 404s for missing users or authorities. Register `admin.router` in `main.py`.

- [ ] **Step 4: Verify GREEN**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_admin.py -q`

Expected: PASS for all authority/user administration tests and manager direct access 403.

### Task 3: Cross-authority data overview and deployment verification

**Files:**
- Modify: `backend/routers/admin.py`
- Modify: `backend/tests/test_admin.py`
- Add: `backend/alembic/versions/012_authority_id_survey_tables.py`
- Add: `backend/alembic/versions/013_backfill_admin_authority.py`
- Add: `backend/alembic/versions/014_users_is_admin.py`

**Interfaces:**
- Produces: ordered `GET /admin/data-overview` authority summaries.

- [ ] **Step 1: Write failing overview test**

```python
def test_admin_data_overview_includes_dataset_counts(client, admin_headers, authority_with_scanner):
    response = client.get("/admin/data-overview", headers=admin_headers)
    assert response.status_code == 200
    authority = next(item for item in response.json() if item["authority_id"] == authority_with_scanner.id)
    assert authority["datasets"]["scanner_raw"]["record_count"] == 1
    assert authority["datasets"]["vaisala"]["record_count"] == 0
```

- [ ] **Step 2: Verify RED**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_admin.py -q`

Expected: FAIL with 404 for `/admin/data-overview`.

- [ ] **Step 3: Implement storage-group aggregation**

```python
def summary_for(model, authority_id, timestamp_column):
    return {"record_count": db.query(func.count(model.id)).filter(model.authority_id == authority_id).scalar(), "last_upload_at": db.query(func.max(timestamp_column)).filter(model.authority_id == authority_id).scalar()}
```

Return SCANNER legacy/raw, CVI legacy/raw, SCRIM raw, reactive legacy/raw/aggregate, network, and Vaisala summaries for every authority. Use each model's matching `ingested_at`, `created_at`, or `rebuilt_at`; empty values are `0` and `null`.

- [ ] **Step 4: Verify API and migration graph**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_admin.py backend/tests/test_validation.py -q`

Run: `Push-Location backend; .venv/Scripts/alembic.exe heads; Pop-Location`

Expected: all tests pass and exactly one Alembic head, `016_users_is_active`.

- [ ] **Step 5: Commit and deploy**

Run: `git add backend/models/user.py backend/routers/auth.py backend/routers/admin.py backend/schemas/admin.py backend/main.py backend/tests/test_admin.py backend/alembic/versions/012_authority_id_survey_tables.py backend/alembic/versions/013_backfill_admin_authority.py backend/alembic/versions/014_users_is_admin.py backend/alembic/versions/016_users_is_active.py`

Run: `git commit -m "feat: add admin management API"`

Run: `git push origin main`

After Railway deploys, record the admin test account JSON response from every requested endpoint and the manager token's `GET /admin/users` 403 response.
