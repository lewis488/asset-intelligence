# Business logic

Domain rules that drive scoring, banding, treatment assignment, and Vaisala DST view construction. Every rule below is enforced in code; formulas and thresholds are cross-referenced in [analytical-models.md](./analytical-models.md).

## Asset composite score (SCANNER + CVI + SCRIM + Reactive)

Implemented in `backend/services/scoring.py`. Composite score is the sum of four components, band membership tuned by env-driven cut points in `backend/config/__init__.py`.

- **CI score (0–40 pts)** — from the latest `scanner_records` row of an asset. `RCI_BAND="Red"` awards the ceiling; Amber scales with `avg_ci`; Green is `max(0, avg_ci / 10)`. A red-percentage bonus of `min(red_pct * 2, 20)` is added.
- **Defect driver score (0–30 pts)** — flat point awards when defect-driver percentages exceed configurable thresholds (LPV, Rutting, Cracking, Texture). Additional bonuses for high red or amber percentages.
- **EDI score (0–15 pts)** — only applied to B and C class roads. Zero below 20; step function up to 15.
- **CVI score (0–65 pts)** — used on unclassified roads instead of SCANNER-based CI. Structural, edge, wearing-course sub-scores capped independently.
- **SCRIM score (0–30 pts)** — 20 base points if `safety_flagged`; up to +10 more scaled by `pct_below_il`.
- **Reactive score (0–30 pts)** — jobs count in a rolling 12-month window plus emergency count in 6-month window, capped, with a fixed recency bonus when the most recent defect is within 90 days.

Risk band assignment (from `config.risk_critical` / `risk_high` / `risk_medium`, defaults 65 / 40 / 20):

- ≥ 65: Critical
- 40–64: High
- 20–39: Medium
- < 20: Low

Treatment recommendation (`_treatment`, `backend/services/scoring.py`): decision tree over `avg_ci` and dominant defect driver. Outputs one of Structural / Inlay / Overlay / Patching / Micro-surfacing / Surface Dressing / Monitoring.

## Vaisala DST scoring

Implemented in `backend/services/vaisala_scoring.py` and ported from `vaisala_dst_handoff/priority_dst.html`. The engine operates in three phases: parse → aggregate → assign.

### Parse

- XLSX and CSV parsers detect columns by fuzzy-match against candidate lists per network config (`stroud`, `wscc`).
- `_recover_hyperlinks_in_df` scans link-shaped columns (regex `link|url|hyperlink|video`) and rewrites cell values from `cell.hyperlink.target`, `=HYPERLINK(...)`, or plain http strings. Columns that look like link columns but yield zero recoverable URLs are returned as `flattened_link_warnings`.
- `_attach_extras_json_column` serialises the recovered link columns plus known passthrough keys (Time UTC, Lat/Lon, Video Link, Map Link, ...) as a JSON string per row and stashes it under `__extras_json`. This travels through aggregation and lands on each interval row's `extras_json` column.
- `_parse_info_sheet` reads the XLSX `Info` sheet for client/district, road class, from/to date, interval length, multiple drives.
- `_dedup_by_latest_pass` groups rows by `(section, from_m, to_m)`. If two or more rows share a key, the row with the greatest parsed `Time UTC` is retained. Fallback (no time column): last row seen. Returns `(df, dup_groups)`.

### Aggregate

- Vectorised scoring: `defect_matrix @ weight_vec / sum(weights) * 100` yields the raw interval score.
- Interval-level primary defect: `argmax(defect_matrix * weight_vec)`.
- Section-level aggregation: length-weighted average of interval scores plus a length-weighted average of every defect-group percentage. Section-level primary/secondary defects are chosen from the section-average defect contribution matrix, not from any single interval.

### Assign (RAG band + treatment)

- `assign_rag(score)` — **fixed** thresholds. `Red ≥ 4.0`, `Amber ≥ 1.8`, else `Green`. Evidence-derived against real WSCC data; not percentile-based; not user-configurable.
- `assign_treatment(structural, alligator, localised, dressing, micro, edge)` — defect-pattern decision tree:
  1. `structural ≥ STRUCTURAL_THRESH` → Resurfacing
  2. `alligator ≥ ALLIGATOR_TIER_THRESH` → Resurfacing
  3. `localised ≥ LOCALISED_THRESH` (or alligator ≥ LOCALISED_THRESH but below the tier threshold) → Patching
  4. `max(dressing, micro) ≥ SURFACE_THRESH` → Surface Dressing when dressing dominates, else Micro-surfacing
  5. `edge ≥ LOCALISED_THRESH` → Patching
  6. Default → Monitor / Patching
- `assign_treatment_percentile(rank_pct)` — alternative percentile-based mode. Percentile rank of each row's `priority_score` (ascending, so worst-scoring rows land at rank 100) maps to `PERCENTILE_TREATMENTS`: `≥90 → Resurfacing`, `≥75 → Surface Dressing`, `≥50 → Micro-surfacing`, else `Monitor / Patching`. Applied over the currently visible view (scale + split) so the ranking is meaningful within a like-for-like set.
- `detect_weight_drift(weights)` — flags any active defect weight that differs from `RAG_VALIDATED_WEIGHTS`. When drift is present the RAG banding is still applied, but the drift is surfaced on the frontend (RAG reliability warning).

## View construction (Vaisala tab)

`backend/routers/vaisala.py` composes each request's row set through `_build_view_rows(db, survey_id, merge_scale, split)`. This is the pivot point where merge scale, split, and treatment mode combine.

### Merge scale

- `section` — persisted `VaisalaSection` rows.
- `100m` — synthesised. Intervals grouped by `section_ref`; `_chunk_respecting_subgroups` splits on `net_reference` sub-groups first to avoid mixing disconnected road stretches, then `_chunk_by_length(100 m)` slices each sub-group. Remainder < 50 m is merged into the last chunk.
- `10m` — raw `VaisalaInterval` rows, one dict per interval, chunk_label `"from-to m"`.

Chunk label is attached to interval-derived rows: `"from-to m"` for 10m, `"from-to m (chunk i/n)"` for 100m, `None` for section-scale.

### Split (Urban / Rural / Combined)

- `urban` — always forces the effective scale to `section` (per the reference brief: urban roads score at whole-section length regardless of the selected scale). Rows are filtered by `urban_rural = 'U'`.
- `rural` — scaled rows filtered by `urban_rural = 'R'`.
- `combined` at non-section scale — urban section rows unioned with rural scaled rows. When no Urban/Rural indicator exists on the survey (e.g. WSCC), combined falls back to the plain scaled row set.

Views with no persisted intervals raise HTTP 422 with a "re-upload the raw file to enable 10m/100m scales" message.

### Treatment mode

`defect` (default) keeps whichever treatment the engine wrote at parse time. `percentile` overwrites the `treatment` field of every row in the current view via `_apply_percentile_treatments` before filter/sort/paginate. Ranking scope is the whole view; filtering by treatment happens after ranking so a percentile filter can be applied downstream without breaking the rank.

## Weight drift semantics

When a caller supplies `weights_json` on `POST /vaisala/upload/raw`, the parser scores against those weights and records per-key deltas from `RAG_VALIDATED_WEIGHTS` in `vaisala_rag_drift_log`. `VaisalaSurvey.has_weight_drift` is set true when at least one row lands in that table. The frontend surfaces a warning banner (`DriftWarning`) that the fixed RAG cutpoints were derived under a specific weight set and drift makes the banding less reliable.

## Deduplication semantics

The dedup rule keys on `(section, from_m, to_m)` — the physical stretch — not on the section alone. Two passes over the same stretch reduce to one; two passes of different length or different `from_m` do not collapse. When time is missing, the "last seen" fallback is deterministic only if the source file's row order is deterministic.

## Export composition

Export is a pure derivation of the view; no state persisted.

- CSV — human-readable column labels (`Section`, `Extent`, `Road Name`, ...). Raw passthrough columns from `extras` are appended at 10m/100m scales only.
- XLSX — CSV columns plus openpyxl styling: dark header, RAG-band fill, treatment fill, hyperlink cells for recovered URL columns.
- SHP — geopandas + pyogrio. Requires an active network geometry layer. Rows are joined by `section_ref → section_key` with a leading-zero normalisation fallback. Emitted as a zipped `.shp/.shx/.dbf/.prj`. Rows that do not match any geometry feature are dropped and reported via response headers.
