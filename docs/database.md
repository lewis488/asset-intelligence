# Database

## Engine

PostgreSQL. SQLAlchemy ORM. Alembic migrations (`alembic/versions/001_initial_tables.py`).
All tables use integer primary keys. Authority isolation enforced at query level via `authority_id` FK.

## Primary Key Convention

NSG reference (`nsg_ref`) is the business key linking all datasets. It is NOT the DB primary key — the surrogate integer `id` is. NSG refs are normalised: leading zeros stripped on ingest, stored as plain string.

## Tables

### `authorities`
One row per highway authority. Fields: `id`, `name`, `created_at`.
Referenced by FK from `users`, `assets`, `network_assets`, `analysis_runs`.

### `users`
`id`, `authority_id` (FK), `email`, `hashed_password`, `is_active`, `created_at`.

### `assets`
Master asset register. One row per `(authority_id, nsg_ref)`.

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| authority_id | FK → authorities | |
| nsg_ref | String, indexed | business key |
| road_name | String | |
| parish | String | |
| road_class | String | A \| BC \| U |
| length_m | Float | often NULL — use network_assets.length_m for analysis |
| geometry | Text | WKT, set from network upload |
| created_at | DateTime | |

Relationships: `scanner_records`, `cvi_records`, `reactive_jobs`, `risk_scores` (all cascade delete).

### `scanner_records` (legacy / simple-CSV path)
One row per upload per asset. Fields: `avg_ci`, `rci_band`, per-parameter defect pcts, amber/red lengths and pcts, CI contributions, `edi_avg`, `survey_year`. Used by legacy `POST /upload/scanner`.

### `scanner_raw_records` (primary / Confirm path)
One aggregated row per `(asset_id, survey_year, offset_direction)`.
Unique constraint: `uq_scanner_raw_asset_year_dir`.

| Column | Notes |
|--------|-------|
| avg_ci | mean CI across all 10m intervals |
| red_pct | % of intervals with CI ≥ 100 (stored as whole %, e.g. 4.35 = 4.35%) |
| amber_pct | % of intervals with 40 ≤ CI < 100 |
| green_pct | % of intervals with CI < 40 |
| max_ci / min_ci | worst and best 10m interval |
| rci_band | Green \| Amber \| Red — Red if red_pct > 0 |
| offset_direction | nearside \| offside \| centre (from OFFSET column: -5 \| 5 \| other) |

### `cvi_records` (legacy / simple-CSV path)
Simple per-upload CVI data. BV224b flags: `structural_flagged`, `edge_flagged`, `wearing_course_flagged`.

### `cvi_raw_records` (primary / Confirm path)
One row per `(asset_id, survey_year)`. Unique constraint: `uq_cvi_raw_asset_year`.

| Column | Notes |
|--------|-------|
| avg_ci_overall | length-weighted average CI_OVRLL |
| max_ci_structural | max across all sub-sections — flag triggers if ≥ 85 |
| max_ci_edge | max — flag triggers if ≥ 50 |
| max_ci_wearingcourse | max — flag triggers if ≥ 60 |
| pct_length_*_flagged | % of section length exceeding each threshold |

### `scrim_records`
One row per `(asset_id, survey_year)`. Unique constraint: `uq_scrim_asset_year`.

| Column | Notes |
|--------|-------|
| mean_sfc | mean SFC excluding SFC=0 rows (zero = no reading, not actual zero) |
| min_sfc | worst SFC excluding zeros |
| sections_below_il | count of 10m intervals with XDIF < 0 |
| pct_below_il | % of total sections (stored as whole %) |
| safety_flagged | True if any XDIF < 0 |
| worst_xdif | most negative XDIF value |
| sfct_threshold | investigatory level for this section |
| dominant_ilct | most common ILCT code (site category) |

### `reactive_jobs` (legacy / simple-CSV path)
Simple per-job reactive data. Fields: `job_ref`, `job_type`, `defect_type`, `job_date`, `cost_gbp`, `response_category`.

### `reactive_job_records` (primary / Confirm path)
One row per job. Unique constraint: `uq_reactive_job_number` on `job_number`.
Filtered on ingest to condition-relevant job types and valid statuses only.
Fields: `priority_category` (1–5), `job_type_category` (pothole/patching/edge/drainage/other), coordinates.

### `reactive_aggregates`
Per `(asset_id, year)` summary rebuilt from `reactive_job_records` on every upload (DELETE+INSERT).
Unique constraint: `uq_reactive_agg_asset_year`.
Fields: `total_jobs_raised`, `emergency_jobs_2hr`, `urgent_jobs_24hr`, `pothole_count`, `patching_count`, `edge_count`, `drainage_count`, `days_since_most_recent_defect`, `jobs_completed`, `jobs_outstanding`, `mean_days_to_completion`, `oldest_outstanding_days`.

Rebuild is done via single SQL INSERT...SELECT (not ORM loop) — `routers/assets.py:1063–1102`.

### `risk_scores`
Stored scoring results (only written when `POST /analysis/run` is called). Fields: `composite_score`, `risk_band`, `ci_score`, `defect_driver_score`, `reactive_score`, `edi_score`, `dominant_defect_driver`, `treatment_recommendation`, `urgency`, `confidence`, `scoring_version`.

Note: on-demand scoring (GET /assets/) does NOT write to this table — it recomputes each request. This table is populated only during analysis runs.

### `analysis_runs`
LLM analysis results. Fields: `summary_text`, `priority_list_json`, `parameters_used`, `authority_id`. One row per triggered analysis.

### `network_assets`
Network geometry master register. One row per `(authority_id, nsg_ref)`. Unique constraint: `uq_network_asset_auth_nsg`.
Populated from GeoPackage or zipped SHP upload. Geometry stored as WKT (EPSG:4326).
Fields: `wsccnet`, `road_class`, `length_m`, `avg_width_m`, `area_m2`, `parish`, `locality`, `district`, `urban_rural`, `speed_limit`, `inspection_freq`, `geometry`.

`network_assets.length_m` is authoritative for analysis — `assets.length_m` is often NULL.

### Vaisala tables (`models/vaisala.py`)
- `VaisalaSurvey` — one survey upload per authority
- `VaisalaSection` — one aggregated row per section per survey
- `VaisalaInterval` — one row per 10m (or configured) interval per survey

Vaisala is authority-scoped but operates as a separate module. Vaisala sections are NOT linked to `assets` table via FK — they use `section_ref` (which may or may not match `nsg_ref`).

## Key Constraints and Invariants

- All percentage fields (red_pct, amber_pct, pct_below_il, etc.) are stored as **whole percentages** (e.g. 4.35 = 4.35%, not 0.0435). This is a hard invariant — past bugs caused by decimal fraction storage.
- Vaisala percentage fields from Excel %-formatted cells: raw value 0.90 → stored as 90.0. Same whole-percentage convention.
- NSG refs normalised: leading zeros stripped before insert.
- Authority isolation: all queries must filter by `authority_id`. No cross-authority data leakage is possible if queries use `current_user.authority_id`.
