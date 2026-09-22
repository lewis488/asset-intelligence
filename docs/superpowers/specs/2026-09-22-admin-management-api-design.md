# Admin Management API Design

## Goal

Provide an admin-only API for authority, user, and cross-authority dataset management. Managers and viewers must never access its data or mutate its resources.

## Scope

The API adds these paths beneath `/admin`:

- `GET /authorities`, `POST /authorities`, and `PATCH /authorities/{id}`
- `GET /users`, `POST /users`, and `PATCH /users/{id}`
- `GET /data-overview`

Public registration remains under `/auth/register` and retains its current behaviour. No frontend is included in this change.

## Authorization

A `require_admin` dependency composes the existing bearer-token authentication and returns 403 unless `current_user.role == "admin"`. Every `/admin` route depends on it, so authorization completes before route code queries or changes cross-authority data.

The user lookup used by authentication will reject inactive users with 401. This prevents both new logins and use of bearer tokens issued before an account was deactivated.

## User lifecycle

`users.is_active` is a non-null Boolean with a server default of `true`. The migration initially gives every existing user `true`, preserving access during rollout. Admin-created users also start active unless the explicitly supported update route later changes that value.

`POST /admin/users` accepts email, password, existing `authority_id`, and one of `admin`, `manager`, or `viewer`. It hashes the password, rejects duplicate email addresses, and returns no password material. `PATCH /admin/users/{id}` can independently update role, authority, and activation state; it rejects a missing target or authority.

## Authority lifecycle

Authority creation accepts name and optional region. Authority updates accept at least one of name or region; a name is stored as submitted after normal Pydantic validation. The API returns 404 for missing authority IDs and 409 for an attempted duplicate authority name.

## Dataset overview

The response is one entry per authority, ordered by authority ID. Each entry contains authority details and a fixed set of dataset summaries: SCANNER, CVI, SCRIM, reactive maintenance, network, and Vaisala. A summary contains record count and `last_upload_at`, the maximum creation timestamp among the backing rows.

For data held in both legacy and Confirm/raw tables, the summary reports individual storage groups as well as a type total. That makes the endpoint unambiguous during the supported legacy-to-raw transition without double-counting a storage group. Empty data is represented by count `0` and `last_upload_at: null`.

## Migration and deployment

Migration `016_users_is_active` expands the user table only; its downgrade removes the column. The deployment commit must also add currently untracked migrations `012_authority_id_survey_tables`, `013_backfill_admin_authority`, and `014_users_is_admin`. They are required ancestors of the tracked `015_role_three_tier` revision. This repairs the Railway migration graph that currently fails at `014_users_is_admin` before the application starts.

The application code remains backwards-compatible while the migration is applied: the column has a database default and the ORM provides a matching default. Railway runs Alembic before Uvicorn, so a successful deployment proves the migration chain can load.

## Error contract

- Missing or invalid bearer token: 401.
- Valid manager or viewer token at any `/admin` route: 403.
- Duplicate user email or authority name: 409.
- Unknown user or authority ID: 404.
- Invalid email, password, role, or no-op patch body: 422.

## Verification

Tests use FastAPI's test client and a test database/session override. They first establish the admin success responses, then prove a manager token receives 403 from `GET /admin/users`. They also cover inactive-user rejection and the major validation/not-found behaviours.

Before frontend work, the API is exercised with the admin test account. The recorded responses demonstrate each endpoint's response shape; no real user passwords or production data are disclosed.
