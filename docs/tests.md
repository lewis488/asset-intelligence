# Tests and coverage

## Present

### Backend

- `backend/tests/test_validation.py` — four unit tests over `services/validation.py`:
  1. Valid SCANNER CSV passes.
  2. Decimal CI values raise a warning.
  3. Missing NSG column blocks upload.
  4. Multi-year file detection.

No other test files. No pytest fixtures, no test database wiring, no factories.

### Frontend

No `*.test.*` files under `frontend/src`. No configured test runner (Vitest / Jest not installed).

## Missing (high-value gaps)

### Vaisala DST

- `parse_raw_xlsx` / `parse_raw_csv` — end-to-end scoring of a small fixture file. Confirm columns, defect proportions, `priority_score`, `worst_interval_score`, primary defect.
- `_dedup_by_latest_pass` — verify two-pass survey collapses to the row with the later `Time UTC`, and the row count on the response matches.
- `_recover_hyperlinks_in_df` — cover `cell.hyperlink.target`, `=HYPERLINK("...")`, and plain-http fallbacks; assert flattened warnings are emitted for suspected link columns that yield nothing.
- `_attach_extras_json_column` — extras propagate through aggregation into `vaisala_intervals.extras_json`.
- `_parse_info_sheet` — client, road_class, from/to dates.
- `assign_rag`, `assign_treatment`, `assign_treatment_percentile` — table-driven unit tests, one per branch.
- `_chunk_by_length` and `_chunk_respecting_subgroups` — remainder < half-target merges into last chunk; multi-`net_reference` groups chunk independently.
- `_build_view_rows` — urban forces section scale; combined at 10m unions urban section + rural 10m; missing intervals raise 422.
- `_apply_percentile_treatments` — ranking ties, single-row edge case, all-null-score edge case.

### Asset scoring

- `compute_scanner_score`, `compute_cvi_score`, `no_data_score` — each threshold branch.
- Treatment decision tree in `_treatment`.
- Composite risk band assignment against `RISK_CRITICAL/HIGH/MEDIUM`.

### Routers

- `POST /vaisala/upload/raw` — full flow with a fixture: upload → assert survey persisted, interval count, RAG summary.
- `GET /vaisala/surveys/{id}/sections` with every combination of `merge_scale`, `split`, `treatment_mode`.
- `GET /vaisala/surveys/{id}/export?format=csv|xlsx|shp` — assert filename, MIME type, first row headers.
- `POST /vaisala/network-geometry/upload` — assert active layer is toggled correctly; previous active flipped to false.
- `GET /vaisala/network-geometry/features` — join by section_key with exact and leading-zero-normalised keys.
- Auth guard: unauthenticated request to every protected endpoint yields 401.

### LLM

- `services/llm.py` — a fake Anthropic client that returns a fixed payload; assert system prompt shape and that `ALL_KNOWLEDGE` is prepended once.

### Ingestion

- `parse_scanner_excel` with a fixture that carries the HMDIF three-row header.
- `parse_cvi_csv`, `parse_reactive_csv`, `parse_network_file` each with representative fixtures.

## Coverage tooling

Not wired. Suggested initial setup:

```
backend/
  pytest.ini              # pytest config, testpaths=backend/tests
  backend/tests/conftest.py   # authority + user + JWT fixtures; SessionLocal override
  backend/tests/fixtures/     # small XLSX/CSV/SHP fixtures under 100 KB
frontend/
  vitest.config.js        # Vitest for React 18 + Vite
  frontend/src/**/*.test.jsx
```

Any change to Vaisala scoring or `_build_view_rows` should carry regression tests before merge.
