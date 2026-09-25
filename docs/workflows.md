# Workflows

End-to-end data flows through the system. Each section describes what runs, in what order, and what manual steps are required.

## 1. SCANNER Data Upload (Confirm Raw)

**Endpoint:** `POST /assets/upload/scanner/raw`
**Trigger:** Manual file selection in Upload UI or direct API call.

1. File bytes received as multipart upload
2. `read_tabular_for_validation()` reads file without full parse
3. `DatasetValidator.validate(df, SCANNER_RAW_SCHEMA)` — checks required columns (NSG, CI_VALUE, SURVEY_DATE, OFFSET), value ranges, unit conventions. Returns 422 if validation fails.
4. If file > 10 MB: `_parse_scanner_raw_chunked()` processes in 10,000-row chunks with running stats. Else: `parse_scanner_raw()` loads full DataFrame.
5. Aggregation: per `(NSG, survey_year, offset_direction)` — avg_ci, red_pct, amber_pct, green_pct, rci_band, total_length_m.
6. For each record: upsert `Asset` (create if NSG not seen for authority), upsert `ScannerRawRecord` (update if exists for same year/direction).
7. DB commit. Return `RawIngestionResult` with records_ingested, assets_created, survey_years, unmapped_columns, validation summary.

**Timeout:** 300 seconds via `asyncio.wait_for`. Large files run in thread executor.
**Manual steps:** None after file selection.

---

## 2. CVI Data Upload (Confirm Raw)

**Endpoint:** `POST /assets/upload/cvi/raw`

1–3. Same as SCANNER: read, validate against `CVI_RAW_SCHEMA` (required: NSG, CI_OVRLL, SECTIONLEN, SURVEY_DATE).
4. `parse_cvi_raw()` — groups by `(NSG, survey_year)`, computes length-weighted avg_ci_overall, domain maximums, BV224b flags, pct_length_*_flagged.
5. Upsert `Asset` and `CviRawRecord` per year.
6. Commit and return result.

---

## 3. SCRIM Data Upload

**Endpoint:** `POST /assets/upload/scrim/raw`

1–3. Validate against `SCRIM_RAW_SCHEMA` (required: NSG, SFC, SURVEYDATE).
4. `parse_scrim_raw()` — groups by `(NSG, survey_year)`, excludes SFC=0 rows from mean/min, computes safety_flagged from XDIF < 0.
5. Upsert `Asset` and `ScrimRecord` per year.
6. Commit and return result.

---

## 4. Reactive Jobs Upload (Confirm Raw)

**Endpoint:** `POST /assets/upload/reactive/raw`

1–3. Validate against `REACTIVE_RAW_SCHEMA` (required: site_code or nsg, job_type_name, status_name).
4. `parse_reactive_raw()` — filter to condition-relevant job types and valid statuses. Derive priority_category (1–5) and job_type_category.
5. Deduplication: skip jobs where `job_number` already exists in `reactive_job_records`.
6. Insert new `ReactiveJobRecord` rows, create `Asset` if needed.
7. Bulk aggregate rebuild for affected `(asset_id, year)` groups:
   - DELETE existing `ReactiveAggregate` rows for affected asset IDs
   - INSERT...SELECT rebuilds all aggregates in two SQL statements
8. Commit. Return result with jobs_ingested, jobs_skipped, jobs_filtered_out, aggregates_rebuilt.

**Note:** Aggregate rebuild is idempotent — safe to upload the same file twice (duplicates skipped by job_number uniqueness).

---

## 5. Network SHP Upload

**Endpoint:** `POST /assets/upload/network`

1. Validate: `read_network_for_validation()` reads first 100 rows of attributes (no geometry load) → `DatasetValidator.validate(df, NETWORK_SHP_SCHEMA)`.
2. `parse_network_file()` in thread executor: reads GeoPackage or unzips SHP, filters to CLASS ∈ {A,B,C,D} and OWNERSHIP == "WEST SUSSEX COUNTY COUNCIL", groups by NSGNO, computes unary_union geometry, reprojects to WGS84.
3. Upsert `NetworkAsset` per NSG.
4. Coverage analysis SQL: counts network NSGs matched to assets with each data type present.
5. Commit. Return `NetworkIngestionResult` with nsgs_ingested, total_length_km, by_class, coverage_analysis.

---

## 6. Vaisala Upload (Raw RoadAI)

**Endpoint:** `POST /vaisala/upload` (routers/vaisala.py)

1. Detect file type (XLSX vs CSV vs ZIP/SHP).
2. XLSX: `parse_raw_xlsx()` — recover hyperlinks from openpyxl, attach extras_json column, dedup by latest pass per `(section, from_m, to_m)`, vectorised interval scoring, section aggregation.
3. CSV: `parse_raw_csv()` — same minus hyperlink recovery.
4. SHP: `parse_shp_export()` — reads pre-scored SHP from priority_dst.html using `SHP_FIELD_MAP`.
5. Persist `VaisalaSurvey`, `VaisalaSection`, `VaisalaInterval` rows.
6. Return section count, drift warnings, dup_groups_resolved, flattened_link_warnings.

**Memory note:** Large Vaisala XLSX files caused OOM at Railway 1 GB default. Memory limit raised to 8 GB. python-calamine used as primary engine for lower memory footprint.

---

## 7. On-Demand Scoring (Asset List)

**Endpoint:** `GET /assets/`
**No manual trigger needed.**

1. Query `Asset` table filtered by `authority_id` (+ optional road_class, parish filters).
2. For each asset, call `_score_asset(asset, db)`:
   - Query latest `ScannerRawRecord`, `CviRawRecord`, `ScrimRecord`, `ReactiveAggregate`
   - Compute component scores and composite
   - Derive treatment recommendation, urgency, cost bands, confidence
3. Sort by composite_score descending.
4. Optional filter by risk_band.
5. Return paginated `PaginatedAssets`.

**Performance note:** Scoring is computed per request and not cached. For large authorities (thousands of assets), this can be slow. No stored/pre-computed scores are used by this endpoint (risk_scores table is not read here).

---

## 8. AI Analysis Run

**Endpoint:** `POST /analysis/run`
**Trigger:** Manual — user clicks "Run Analysis" in UI.

1. `_build_scored_assets()` — score all assets for authority, accumulate stats (CI values, band counts, RCI band lengths, network coverage).
2. Build stats dict with network-level KPIs (mean CI, red %, amber %, total length, dataset coverage).
3. Construct LLM prompt: top N priority assets + stats dict as user message.
4. Call `generate_analysis()` in `services/llm.py` — Anthropic API with cached system prompt.
5. Persist `AnalysisRun` with summary_text and priority_list_json.
6. Return analysis summary.

---

## 9. AI Query

**Endpoint:** `POST /analysis/query`
**Trigger:** Manual — user submits question in Query UI.

1. Load latest `AnalysisRun` for authority.
2. Build user message from query + existing analysis context.
3. Call `answer_query()` in `services/llm.py`.
4. Return response text. Not persisted.

---

## 10. Priority List Export

**Endpoint:** `GET /assets/export`

1. Query all assets for authority.
2. Score each via `_score_asset()`.
3. Sort by composite_score descending.
4. Write CSV with fields: nsg_ref, road_name, parish, road_class, length_m, composite_score, risk_band, scanner_score, cvi_score, scrim_score, reactive_score, score_completeness, dominant_dataset, survey_year, has_scanner, has_cvi, has_scrim, has_reactive.
5. Stream as `Content-Disposition: attachment; filename=priority_list.csv`.

**Note:** treatment_recommendation is NOT included in export CSV. Only available via `/assets/by-nsg/{nsg_ref}` or the JSON list endpoint.

---

## 11. Map Data

**Endpoint:** `GET /assets/map-data`

Single SQL query joining `network_assets` → `assets` → `risk_scores` (latest) → `scanner_raw_records` (latest). Returns GeoJSON FeatureCollection with geometry from `network_assets.geometry` (WKT → shapely → GeoJSON mapping). Only NSGs with non-null geometry are included.

Filters: `road_class`, `risk_band`, `rci_band` (applied in Python post-query).
