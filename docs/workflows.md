# User workflows

End-to-end paths through the system. Each workflow lists the frontend entry point, the endpoints hit, and the backend side-effects.

## Sign in

1. `frontend/src/pages/Login.jsx` submits email + password.
2. `authApi.login` posts an OAuth2 password-form body to `POST /auth/login`.
3. Backend `create_access_token` returns a `{ access_token, token_type, user }` payload; token has an 8-hour expiry.
4. `AuthContext.login` writes `ai_token` and `ai_user` to `localStorage`, then redirects to `/dashboard`.
5. Subsequent requests carry `Authorization: Bearer <token>` via the axios request interceptor.

## Ingest SCANNER data → score → view priorities

1. User navigates to `/upload` and picks the SCANNER Raw block.
2. `assetsApi.uploadScannerRaw(file)` POSTs the file to `/assets/upload/scanner/raw` (300 s timeout).
3. Backend validates via `DatasetValidator`, parses via `parse_scanner_raw`, bulk-inserts into `scanner_raw_records`.
4. Response returns a `ValidationResult` (errors, warnings, info, detected survey years, row count).
5. User goes to `/analysis` and clicks Run Analysis. `analysisApi.run()` hits `POST /analysis/run`.
6. Backend scores every asset via `compute_scanner_score` (and `compute_cvi_score` where applicable), builds an aggregate stats block, calls `generate_analysis` on the LLM, and persists an `AnalysisRun` row.
7. `/analysis` renders `AIBriefing`, `DefectDriverChart`, and `PriorityList` from the returned run.

## Ingest a Vaisala raw survey → view → export

1. `/vaisala` → `UploadPanel` picks a `.xlsx` or `.csv` file, network key (`stroud` or `wscc`), dedup strategy (`latest` or `none`), and optional custom defect weights.
2. `vaisalaApi.uploadRaw(file, networkKey, weights, dedupStrategy)` posts to `POST /vaisala/upload/raw` (300 s timeout).
3. Backend:
   - Reads bytes.
   - Runs `_recover_hyperlinks_in_df` and `_attach_extras_json_column` (XLSX only).
   - Applies `_dedup_by_latest_pass` when the strategy is `latest`.
   - Runs `_aggregate_intervals` (scored interval and section rows).
   - Calls `_parse_info_sheet` on the XLSX for client/date/interval metadata.
   - Persists `VaisalaSurvey` + `VaisalaSection` + `VaisalaInterval` + optional `VaisalaRagDriftLog` rows.
   - Returns a `VaisalaUploadResult` (survey id, RAG summary, drift details, dup count, info meta, flattened-link warnings).
4. `Vaisala.jsx` receives the result, selects the new survey, and renders:
   - `RagStrip` (from `stats(surveyId, view)`).
   - Treatment mix strip.
   - Tab bar with `list1..list4`, `correlation`, `qc`, `map`.
   - Merge scale, split, and treatment-mode toggles.
5. `ListTab` requests `/vaisala/surveys/{id}/sections` with the current view params. `CorrelationTab` and `QCTab` request `/sections/all`. Every request re-runs `_build_view_rows` server-side.
6. Export buttons on `ListTab` call `/vaisala/surveys/{id}/export?format={csv|xlsx|shp}`. CSV and XLSX are always available; SHP requires an active network geometry layer.

## Upload a Vaisala scored SHP export (pre-scored)

1. `UploadPanel` switches to the `shp` mode and picks a `.zip` containing the priority_dst.html SHP export.
2. `vaisalaApi.uploadShp(file, networkKey)` posts to `POST /vaisala/upload/shp`.
3. Backend `parse_shp_export` reads the zipped shapefile via geopandas + pyogrio, extracts pre-scored section data (no interval-level records), persists `VaisalaSurvey` + `VaisalaSection`. `has_weight_drift` is always `false` on this path (scoring already happened upstream).
4. The user sees the survey exactly like a raw upload but 10m and 100m merge scales are disabled (no intervals exist to synthesise from).

## Upload a network geometry (map basemap join)

1. On the Map tab, `NetworkGeometryUploadPanel` accepts a `.zip` containing `.shp/.shx/.dbf/.prj` and an optional `section_field` (DBF column that identifies each section).
2. `vaisalaApi.uploadNetworkGeometry(file, sectionField)` posts to `POST /vaisala/network-geometry/upload`.
3. Backend extracts the zip to a temp dir, reads via geopandas, auto-detects `section_field` (`SECTIONLAB` → any column containing `section` or `nsg` → first attribute), reprojects to EPSG:4326, deactivates any prior active layer, and bulk-inserts per-feature `geometry_geojson` records.
4. Response returns the layer id, feature count, and available DBF field names for section_field disambiguation.

## Render the map

1. `MapTab` bootstraps a Leaflet map with an OS Maps `Light_3857` tile layer when `VITE_OS_MAPS_API_KEY` is set, or OpenStreetMap tiles as a fallback.
2. On mount and whenever `view` changes, `vaisalaApi.networkFeatures(surveyId, view)` requests `GET /vaisala/network-geometry/features?survey_id=…`.
3. Backend loads the active network geometry, runs `_build_view_rows` for the current view, applies percentile treatment if requested, joins on `section_ref → section_key` (with leading-zero normalisation), and returns a GeoJSON `FeatureCollection` with per-feature `matched` flag plus the full property set (score, band, treatment, defect breakdown, source measures).
4. The frontend renders a coloured GeoJSON layer (by `rag_band`, `treatment`, or a green→amber→red gradient over `priority_score`). Clicks open `SectionDetailPanel`; hover thickens the stroke.

## Query the network (multi-turn LLM chat)

1. `/query` collects a question. `analysisApi.query(question, history)` posts to `POST /analysis/query`.
2. Backend rebuilds the asset context, prepends the cached `ALL_KNOWLEDGE` system prompt, and calls the Anthropic client with the running conversation history.
3. Response is a plain string returned by the LLM; the frontend appends it to the on-screen thread.

## Export

CSV/XLSX from the assets side hits `GET /assets/export` (StreamingResponse). Vaisala CSV/XLSX/SHP hits `GET /vaisala/surveys/{id}/export?format=…`. SHP is streamed as `application/zip` with headers `X-Rows-Written` and `X-Rows-Skipped-Unmatched` so the frontend can surface a mismatch note.
