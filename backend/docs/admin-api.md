# Admin management API

All seven endpoints require a bearer token for an active admin. Managers and
viewers receive 403, including direct API requests. Missing authentication or
inactive accounts receive 401. Role and authority changes apply to existing
tokens because authentication reloads the user on each request.

| Method | Path | Response |
| --- | --- | --- |
| GET | /admin/authorities | 200 array of {id, name, region} |
| POST | /admin/authorities | 201 authority; input name, optional region |
| PATCH | /admin/authorities/{id} | 200 authority; input name and/or region |
| GET | /admin/users | 200 array of {id, email, authority_id, role, is_active} |
| POST | /admin/users | 201 user; input email, password, authority_id, role |
| PATCH | /admin/users/{id} | 200 user; input role, authority_id and/or is_active |
| GET | /admin/data-overview | 200 {authorities: [...], total_authorities} |

Creation supports admin, manager and viewer roles; passwords require 8–72 UTF-8
bytes and are hashed. No password material is returned. Public /auth/register
continues to support manager/viewer registration, but rejects admin creation.
Migration 016 adds is_active with true as both database and ORM default.

Patches require at least one supported field. Explicit null is rejected except
for region, where it clears the value. Missing records or authorities return
404, duplicate user email returns 409, invalid input returns 422.

Overview includes every authority, even those without data. Each authority has
authority_id, authority_name and datasets. Dataset keys are scanner, cvi, scrim,
reactive, network, vaisala and vaisala_network. Each has record_count and
last_upload_date (ISO datetime or null). Empty datasets have count 0.

Counts represent retained database rows, not unique roads or Excel source rows.
SCANNER, CVI and reactive counts combine legacy and Confirm tables. Vaisala counts
intervals where present, otherwise sections (SHP uploads). Vaisala network counts
stored geometry features. Derived aggregates are excluded. Dates are the latest
ingestion timestamp on retained rows, not survey dates or a permanent upload log.
Upsert paths that retain an original ingestion timestamp cannot expose subsequent
upload times without a separate audit history.

Verification: backend/tests/test_admin.py covers all routes for manager/viewer
denial, admin CRUD, active-token revocation, public admin-registration denial,
input validation, legacy/raw counts, empty datasets and Vaisala SHP counts.
