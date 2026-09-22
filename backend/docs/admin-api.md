# Admin management API

All admin endpoints require a bearer token for an active admin. Managers and
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
| DELETE | /admin/users/{id} | 204; self-deletion returns 409 |
| DELETE | /admin/authorities/{id} | 204; users or source data remaining returns 409 |
| GET | /admin/authorities/{id}/uploads | 200 list of retained source files and individual Vaisala uploads |
| DELETE | /admin/authorities/{id}/datasets/{type} | 204; selects exactly one source file or upload ID in the JSON body |

Creation supports admin, manager and viewer roles; passwords require 8–72 UTF-8
bytes and are hashed. No password material is returned. Public /auth/register
is disabled and always returns 403; the login page only supports sign-in.
Authorities and users must be created through Admin.
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
denial, admin CRUD, active-token revocation, public registration denial,
input validation, legacy/raw counts, empty datasets and Vaisala SHP counts.

## Deletion

The UI offers Delete actions in Authorities and Users. Data Overview retains its
dataset cards and adds a Manage uploads list for each authority. Each deletion
dialog identifies the target and requires its name/email/filename to be typed.
Deletion is permanent. The current user cannot delete their own account; deleting
another user immediately invalidates that user's existing tokens.

An authority must have no users, source records, Vaisala surveys or network geometry
uploads. Zero-record surveys and geometry uploads are still dependencies and appear
in Manage uploads. After these are removed, authority deletion clears any remaining
derived analysis, reactive aggregates and empty asset shells in the same transaction.
Unexpected foreign-key dependencies return 409 and roll back the transaction.

Upload list entries contain dataset_type, source_file (nullable), upload_id
(nullable), record_count and uploaded_at (nullable). Supported types match the
overview: scanner, cvi, scrim, reactive, network, vaisala, vaisala_network.

- Vaisala surveys and geometry layers each have a distinct upload_id, even when
  filenames match. DELETE requires exactly `{"upload_id": 123}`. Intervals,
  sections, drift logs or geometry features are deleted with their parent upload.
- Other types lack upload-history IDs. They list retained records grouped by exact
  source_file across legacy/raw tables within that authority and dataset type.
  DELETE requires exactly `{"source_file": "survey.csv"}`. Repeated imports with
  the same filename form one group; overwritten/upserted historical rows cannot be
  recovered or independently deleted. Dates reflect the latest retained ingestion
  timestamp, not a complete upload history. The UI discloses this limitation.
- An explicit `{"source_file": null}` targets only legacy records lacking a
  filename, shown as Unattributed records. An omitted target, wrong target kind,
  mixed selectors or unknown dataset type returns 422. A missing target returns 404.

Every selection is scoped to an explicit authority. Raw/legacy records follow their
asset's authority, including rows with an unpopulated redundant authority_id.
Deleting a dataset invalidates saved RiskScore and AnalysisRun rows for its authority.
Reactive source deletion rebuilds aggregates from retained jobs using the same SQL
aggregation helper as uploads. Narrative caches check live records and current input
context before returning a cached response, including across separate API workers.
Analysis generation and deletion lock the same authority row to prevent in-flight
analysis from recreating stale saved results after deletion.

Tests: test_admin_deletion.py covers permissions, scoped deletion, retained sibling
files/surveys, token revocation, dependency guards, aggregate rebuilding and narrative
cache invalidation. test_admin_postgres.py verifies actual PostgreSQL lock ordering
and date arithmetic in a disposable local schema when ADMIN_TEST_POSTGRES=1; it
rejects non-local database hosts. The frontend browser suite runs with
`npm run test:admin`; ADMIN_BASE_URL can point to a deployed frontend. All API data
and mutations in that suite are intercepted, so it does not modify live records.
