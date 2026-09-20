# Technical Debt

## Two RoadIQ+ Implementations: Production and Standalone/Experimental

**Severity: Low — intentional architecture, not a defect.**

The RoadIQ+ model has two implementations at this build stage — a live production scorer and a standalone/experimental variant. Both operate on Confirm-format data. They are NOT a drifted copy of the same logic; they diverge by design.

### RoadIQ+ production: `routers/assets.py:_score_asset()` (lines 46–276)
Built for Confirm-format datasets (SCANNER raw 10m, CVI raw, SCRIM raw, reactive aggregates, network geometry).
- Live production scorer. Called by `GET /assets/`, `GET /assets/export`, `POST /analysis/run`.
- Four components: SCANNER (0–60 pts), CVI (0–65 pts), SCRIM (0–30 pts), reactive (0–30 pts).
- Coupled to SQLAlchemy session — queries DB directly.

### RoadIQ+ standalone/experimental: `services/scoring.py`
A standalone RoadIQ+ variant with defect driver analysis. NOT called by the production API.
- `compute_scanner_score()`, `compute_cvi_score()`, `no_data_score()`.
- Uses `ci_contribution_*` columns (Confirm HMDIF Excel) for defect driver analysis — rutting, cracking, texture, LPV proportions drive treatment selection.
- All weights env-configurable via `config.settings`.
- No SCRIM component.
- Clean, no FastAPI or SQLAlchemy imports — designed to be separable.

`scoring.py` has a materially different input set (`ci_contribution_*` defect proportions from HMDIF Excel) and different scoring logic (defect driver analysis, EDI). `_score_asset()` covers SCRIM and uses simpler RCI-band-based arithmetic. Both are Confirm-format. Neither is a Vaisala model.

**Note:** `services/vaisala_scoring.py` is a third, entirely separate model (RoadIQ) for Vaisala RoadAI data. It is not part of this two-implementation comparison. See business-logic.md § Vaisala Business Logic.

### Genuine side-effect worth noting (Low severity)
`config.settings` exposes env vars for defect driver weights (`DD_LPV_POINTS`, `DD_RUTTING_POINTS`, etc.) that feed `scoring.py` but have no connection to `_score_asset()`. Tuning these env vars has no effect on live scores. This is not a bug — it reflects `scoring.py` being standalone — but it could mislead a future developer who reads the config and assumes these weights affect production output.

### Roadmap item (not debt)
Future unification: linking RoadIQ (`vaisala_scoring.py`) and RoadIQ+ (`_score_asset()`) data so treatment selection and programme costing draw on both models jointly. At that point `scoring.py`'s defect driver logic and `vaisala_scoring.py`'s treatment tree would feed a single composite recommendation layer. This is a planned next stage of development, not a defect fix.

Cross-reference: business-logic.md § Two RoadIQ+ Implementations.

---

## Hardcoded: Treatment Cost Bands

**Severity: Medium.**

Treatment cost bands in `routers/assets.py:_score_asset()` (lines 148–200) are hardcoded £/m² ranges:
- Urgent reconstruction: £80–150/m²
- Inlay/reconstruction: £45–80/m²
- Inlay (mill and fill): £20–45/m²
- Thin surfacing: £12–20/m²
- Surface dressing/micro-asphalt: £5–14/m²
- Edge treatment: £25–38/m²

These are not env-configurable. They are not validated against current market rates. Other authorities' cost structures will differ. The README scoring model table also shows different max points to what `_score_asset()` actually implements.

---

## Absent: Total Cost Per Section

**Severity: Medium.**

`cost_low_per_m2` and `cost_high_per_m2` are returned per section but are unit rates only. No multiplication by section length occurs in the application. An authority using this to estimate programme cost must do their own arithmetic. Total cost is not surfaced in the export CSV or AI briefing.

---

## Hardcoded: Network Ownership Filter

**Severity: Medium (blocks multi-authority use).**

`services/ingestion.py:parse_network_file()` line 1206:
```python
_NETWORK_OWNER = "WEST SUSSEX COUNTY COUNCIL"
```
and line 1253:
```python
gdf = gdf[
    gdf["CLASS"].isin(_NETWORK_VALID_CLASSES) &
    (gdf["OWNERSHIP"] == _NETWORK_OWNER)
].copy()
```

Any authority other than WSCC uploading their network file will get zero features after this filter. Must be made configurable per authority before the platform is genuinely multi-authority.

---

## Hardcoded: Reactive Job Type Filter

**Severity: Low–Medium.**

`services/ingestion.py:_REACTIVE_INCLUDE_TYPES_LOWER` (line 1026–1033):
```python
_REACTIVE_INCLUDE_TYPES_LOWER: list[str] = [
    "potholes | cway",
    "patching | cway",
    "verge repairs",
    "kerb | edge works",
    "covers | gullies cway",
]
```

These are WSCC Confirm job type name strings. Other authorities use different Confirm job type naming conventions. Ingest from another authority will silently filter out all or most reactive jobs unless these strings match their naming.

---

## Legacy / Simple Upload Paths Not Retired

**Severity: Low.**

Two sets of upload endpoints and DB tables exist:

| Path | Tables | Endpoints |
|------|--------|-----------|
| Legacy (simple CSV/Excel) | scanner_records, cvi_records, reactive_jobs | POST /upload/scanner, /upload/cvi, /upload/reactive |
| Primary (Confirm raw) | scanner_raw_records, cvi_raw_records, scrim_records, reactive_job_records, reactive_aggregates | POST /upload/scanner/raw, /upload/cvi/raw, /upload/scrim/raw, /upload/reactive/raw |

`_score_asset()` queries `scanner_raw_records` and `cvi_raw_records` (primary tables). Data uploaded via legacy endpoints goes into `scanner_records` / `cvi_records` which `_score_asset()` does NOT query. Legacy uploads silently succeed but contribute nothing to scores. This is a potential source of user confusion.

---

## Vaisala Not Integrated into Main Composite

**Severity: Low (by design, but worth recording).**

Vaisala scoring operates as a separate module. `VaisalaSection` is not linked to `assets` table via FK. Vaisala scores do not contribute to `composite_score` in `_score_asset()`. An authority with Vaisala data sees two separate priority lists that cannot be directly compared.

---

## QC Metrics Not Implemented

**Severity: Low.**

`qc_completeness_pct`, `qc_completeness_band`, `qc_reliability_pct`, `qc_reliability_band` fields exist in `VaisalaSection` schema and are referenced in `SHP_FIELD_MAP`. In `_aggregate_intervals()` (line 461–463) they are set to `None` for all records produced from raw XLSX/CSV. Only populated when importing from a pre-scored SHP export. No calculation logic exists.

---

## No Test Suite

**Severity: Medium.**

No `tests/` directory was found. No pytest fixtures, unit tests, or integration tests exist in the backend codebase. The `.claude/agents/test-engineer` subagent is defined but no tests have been written. Validated benchmarks (mean CI, red %) were confirmed manually against real data, not via automated regression tests.

---

## README.md Is Stale

**Severity: Low (documentation, not code).**

`README.md` at project root does not reflect current functionality:
- No mention of Vaisala, SCRIM, or network SHP ingestion
- Wrong backend port (shows 8000, correct is 8001)
- Wrong import convention (shows `backend.main:app`, correct is `main:app` for Railway flat imports)
- Scoring model table reflects neither `scoring.py` nor `_score_asset()` accurately
- API reference table is incomplete (missing all raw Confirm endpoints, Vaisala router, map-data, network-stats)

README is the first point of contact for external reviewers. Its inaccuracy is a due-diligence risk.

---

## Prompt Cache Miss Risk on High Request Volume

**Severity: Low.**

`services/llm.py` uses Anthropic prompt caching on system prompt and dataset context. Cache TTL is 5 minutes. On high-traffic deployments with analysis queries spaced > 5 minutes apart, cache misses will significantly increase token cost and latency. No cache warming mechanism exists.
