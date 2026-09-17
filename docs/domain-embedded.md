# Domain-embedded logic

Constants, thresholds, and decisions currently baked into code that would be better lifted into config or a shared source of truth.

## Vaisala DST — hard-coded in `backend/services/vaisala_scoring.py`

### RAG thresholds (fixed, evidence-derived — see priority_dst.html rationale)

- Red ≥ 4.0
- Amber ≥ 1.8
- Green < 1.8

Exposed as module-scope constants; not configurable via env vars. Rationale documented in the ported comments (they were derived against real WSCC survey data; changing them silently would break RAG comparability across surveys).

### Treatment thresholds (defect-pattern mode)

Named constants at module scope (`STRUCTURAL_THRESH`, `ALLIGATOR_TIER_THRESH`, `LOCALISED_THRESH`, `SURFACE_THRESH`). Same rationale as the RAG cutoffs: derived alongside `RAG_VALIDATED_WEIGHTS`, treated as part of the "validated" set.

### Percentile treatment band cutoffs

`PERCENTILE_TREATMENTS` list literal: 90 / 75 / 50 / 0. Directly matches the priority_dst.html `DEFAULT_TREATMENTS`. No env override.

### Defect group membership

`STRUCTURAL_KEYS`, `LOCALISED_KEYS`, `DRESSING_KEYS`, `MICRO_KEYS`, `EDGE_KEYS`, `ALLIGATOR_KEY` — the mapping from raw defect labels to grouped treatment inputs. Also mirrors priority_dst.html but expressed in code rather than data.

### Weight set

`RAG_VALIDATED_WEIGHTS` — dict literal. See `analytical-models.md` for the table. Not easy to override at runtime (a caller can pass `weights_json`, but only that specific request uses them; there is no admin UI or persisted alternative weight set beyond the drift log).

### Column candidate lists

`NETWORK_CONFIGS` — per-network dictionary of candidate column names for section, road name, urban/rural, road class, net reference. Also declares capabilities (`has_urbrur`, `has_rsc`). New networks require a code change.

### Passthrough keys for extras

`_EXTRA_PASSTHROUGH_KEYS` — hard list of column names copied into `extras_json` when found (Time UTC variants, Lat/Long variants, Video/Map links). New passthrough keys require a code change.

## Asset scoring — `backend/services/scoring.py`

The bulk of thresholds and point awards *are* config-driven (see [analytical-models.md](./analytical-models.md)). Exceptions still in code:

- CVI sub-score divisors (`ci / 85 * 40`, `ci / 50 * 15`, `ci / 60 * 10`) — magic denominators in `compute_cvi_score`.
- Reactive recency bonus (+5, 90-day window) — magic numbers in `_reactive_score`.
- Treatment string names (`"Resurfacing"`, `"Micro-surfacing"`, ...) — repeated across `scoring.py`, `vaisala_scoring.py`, and the frontend legend. No single source of truth.

## Routers — `backend/routers/`

- `_LINK_HDR_PATTERN` (regex for URL-shaped export columns) and `RAG_FILL`, `TREATMENT_FILL` (openpyxl ARGB fills) live in `routers/vaisala.py`. Duplicated conceptually with the frontend colour tokens.
- Upload cap `_MAX_UPLOAD_BYTES = 500 * 1024 * 1024` in `routers/assets.py`. Fine as an operational choice but not configurable.
- Auth JWT `_EXPIRE_HOURS = 8` in `services/auth.py`.

## Frontend — `frontend/src/pages/Vaisala.jsx`

- `RAG_COLOUR` object literal.
- `MAP_TREATMENT_COLOURS` object literal.
- `MERGE_SCALES`, `SPLITS`, `TREATMENT_MODES` labels + descriptions.
- Score-to-colour gradient (`scoreToColour`) uses fixed anchor colours `#7a9b6e → #d9a51c → #c0432f` and a 0–10 domain assumption.
- Symbology legend labels are inline strings.

## What "shared source of truth" would look like

A minimal cleanup:

1. Emit a small JSON manifest at build time from a Python source-of-truth (e.g. `backend/domain_constants.py`).
2. Frontend imports the same JSON via a Vite alias or `?raw` import.
3. Every colour, band label, treatment name, and merge-scale key stays in one file.

Alternative: keep them independent but add a doc-level assertion (a linter or a CI test) that the frontend and backend maps agree on band names.

## Not domain-embedded — call out for clarity

- CI, defect-driver, EDI, reactive scoring thresholds are already env-driven via `backend/config/__init__.py`. Nothing to lift there.
- Frontend axios base URL is env-driven (`VITE_API_BASE_URL`).
- Scoring version tag is env-driven (`SCORING_VERSION`), stamped on every persisted `RiskScore` row.
