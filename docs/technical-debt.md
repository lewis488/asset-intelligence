# Technical debt

Concrete opportunities. Each item lists file references and the observable symptom.

## Long modules candidate for splitting

- `backend/services/vaisala_scoring.py` (~700 lines) — scoring + parsing (XLSX/CSV/SHP) + hyperlink recovery + info-sheet reader + dedup all in one module. Natural split: `vaisala_scoring.py` (scoring + aggregation), `vaisala_parsing.py` (`parse_raw_*`, `parse_shp_export`, dedup), `vaisala_extras.py` (hyperlink recovery + info sheet).
- `backend/services/ingestion.py` (~1200 lines) — every asset-side format parser (SCANNER, CVI, SCRIM, Reactive, Network, plus the raw Confirm-export variants). Natural split: one module per format.
- `frontend/src/pages/Vaisala.jsx` (~1300 lines) — every Vaisala tab plus the upload panel plus the map. Natural split: `VaisalaPage.jsx` shell, `VaisalaUploadPanel.jsx`, `VaisalaListTab.jsx`, `VaisalaCorrelationTab.jsx`, `VaisalaQcTab.jsx`, `VaisalaMapTab.jsx`.
- `backend/routers/assets.py` (~800 lines) — endpoint definitions + scoring wiring + export builder. Natural split: `assets_routes.py`, `assets_export.py`.

## Long functions

- `_aggregate_intervals` in `backend/services/vaisala_scoring.py` — vectorised scoring, per-interval dict build, per-section aggregation all in one body. Splitting the section loop out of the per-interval build would let the two halves be tested independently.
- `parse_scanner_excel` and `parse_reactive_csv` in `backend/services/ingestion.py` — header detection + column mapping + aggregation in one call.
- `_score_asset` and `_build_scored_assets` in the assets router — composite score assembly is inline with the endpoint handler.

## Duplicated constants

- RAG colour hex codes appear in `frontend/src/pages/Vaisala.jsx` and again in `backend/routers/vaisala.py` (`RAG_FILL` for XLSX export). A shared source of truth (e.g. a `constants.md` and matching JSON generated for both sides) would keep them in sync.
- Treatment colour hex codes appear in both `frontend/src/pages/Vaisala.jsx` (`MAP_TREATMENT_COLOURS`) and `backend/routers/vaisala.py` (`TREATMENT_FILL`).
- Percentile treatment band cutoffs (90 / 75 / 50) live in `backend/services/vaisala_scoring.py` (`PERCENTILE_TREATMENTS`) with no frontend equivalent — safe today, but the moment a legend or tooltip on the frontend needs the same numbers, they will drift.

## Missing input validation / hardening

- `POST /vaisala/upload/raw` — `weights_json` is parsed with `json.loads` and cast, but individual keys are not checked against `RAG_VALIDATED_WEIGHTS`; a caller can inject arbitrary defect keys that never make it into scoring.
- `POST /analysis/query` — no rate limit. A malicious client can spike Anthropic costs.
- `GET /assets/` and `GET /vaisala/surveys/{id}/sections` — `limit` has an upper bound (200 in the Vaisala case) but no cross-authority quota; a malicious authority could scrape aggressively.
- `POST /vaisala/upload/shp` — 500 MB body limit is global; no per-user or per-authority cap.

## Error handling gaps

- `backend/services/llm.py` catches broad exceptions and returns a generic 500 to the user; no retry or backoff on transient Anthropic errors.
- `_recover_hyperlinks_in_df` catches bare `Exception` twice (once around `openpyxl` import, once around `load_workbook`) — a real IO failure silently degrades to "no links recovered" with no surfaced warning.
- SHP export in `backend/routers/vaisala.py` catches generic exceptions from `gdf.to_file` and returns a 500 with the raw exception message; that message can leak filesystem paths.

## Uvicorn reload flakiness on Windows

Observed during development: `WatchFiles` occasionally misses `backend/routers/vaisala.py` edits until a second file is touched or the process is restarted. Not a code defect per se, but worth a note in a developer onboarding doc.

## No integration tests around the Vaisala pipeline

`backend/tests/test_validation.py` is the only test module and it covers only SCANNER validation. There is zero coverage of:

- `parse_raw_xlsx` / `parse_raw_csv` (dedup, hyperlink recovery, info sheet)
- `_aggregate_intervals` (scoring, primary defect, weighted aggregation)
- `assign_rag`, `assign_treatment`, `assign_treatment_percentile`
- `_intervals_to_100m_sections` (chunking, sub-group split, remainder handling)
- `_build_view_rows` (urban-always-section, combined union)
- SHP export path
- Any router-level test

## Auth surface

- JWT `sub` is the user id but there is no scope claim. Every authenticated user can call every endpoint. Role-based access (already an ORM column on `users.role`) is stored but not enforced.
- `POST /auth/register` allows creating an arbitrary authority; no invitation, no admin check. Suitable for an internal tool but not production-ready.

## Frontend state

- `Vaisala.jsx` holds a large blob of local state (`activeTab`, `mergeScale`, `split`, `treatmentMode`, `selectedSection`, `stats`, `surveys`, ...). No global store. Fine while the page is monolithic; a first step in splitting the file would be to lift to a `useReducer` or introduce a small Context.
- axios `401` interceptor performs a hard redirect; state kept in memory (e.g. an in-flight upload) is silently lost.

## Docs / DX

- No `CLAUDE.md` at repo root. Onboarding relies on `README.md` and reading source.
- No pre-commit hooks or linter config (ruff, black, eslint) in the repo. Style is enforced by convention only.
- Alembic requires the backend `.env` to be sourced before running `alembic upgrade head`; there is no wrapper script that does this. See the CLI hint in [workflows.md](./workflows.md).
