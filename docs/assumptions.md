# Assumptions

Implicit invariants the code relies on. None of these are enforced by type checks; violation surfaces as unexpected behaviour rather than an error.

## Tenancy

- Every request is single-authority. `get_current_user` yields a `User` with an `authority_id`; every query filter uses it. There is no cross-authority read path today.
- One authority owns one active `vaisala_network_geometries` row at a time. The upload endpoint enforces this by deactivating any previous active row for the same authority, but a manual DB edit could break the invariant and the map endpoint would then pick "the most recently created active row".

## Vaisala survey data

- A raw upload always contains at least a `section_col`, `from_col`, and `to_col` recognisable via one of the candidate names in `NETWORK_CONFIGS`. If not, dedup silently returns the input unchanged and aggregation may misbehave.
- `Time UTC` column, when present, is parsable by `pd.to_datetime`. Rows with unparseable timestamps are treated as "no time" and fall back to last-seen deduplication.
- `from_m` and `to_m` are metric offsets in the same coordinate system. Mixed units would corrupt the 100m chunker.
- Defect columns are proportions in `[0, 1]`. Rows with values > 1 will still score, but the resulting `priority_score` will be off-scale (and the fixed RAG cutoffs assume the standard proportion range).
- `Interval Length` (in metres) defaults to 10.0 when null or non-positive. The 100m chunker uses this as a fallback but a survey with mostly-null lengths will chunk unpredictably.
- `RAG_VALIDATED_WEIGHTS` was calibrated against real WSCC data. The fixed 4.0 / 1.8 cutoffs are only meaningful against that weight set; drift detection flags departures but the banding is still emitted.
- 10m and 100m merge scales are only available if intervals were persisted at upload time. Older surveys uploaded before migration 008/009 have no interval rows; the endpoint returns HTTP 422 and the frontend surfaces "re-upload the raw file to enable 10m/100m scales".

## Network geometry

- The uploaded SHP contains one geometry per road section, keyed by the DBF field named by `section_field`. Auto-detection tries `SECTIONLAB`, any column containing `section`, then any column containing `nsg`, then the first attribute column. Silent fallback means a misnamed `section_field` produces zero-match features on the map.
- CRS is either declared (`prj` present) or assumed. If declared, the loader reprojects to EPSG:4326. If not declared, geopandas emits a warning but still passes through untouched — the map layer will be geographically incorrect.
- Section key matching normalises leading zeros only for purely numeric keys. Mixed-format keys (e.g. `SR-01234`) match only exact.

## SCANNER, CVI, SCRIM, Reactive uploads

- `parse_scanner_excel` assumes the HMDIF three-row header layout. Files that omit the "CI DISTRIBUTION" section will still parse but yield null defect-driver contributions.
- CVI CI values are expected in the whole-number range. Decimal values (0–1) trigger a validation warning, not a hard failure, on the assumption the client made a units mistake.
- Reactive job dates are UK-formatted strings. Non-UK date formats parse to NaT and are then dropped from the recency windows.

## Auth

- `role` on `users` is a free-form string. Nothing enforces the set of allowed values or acts on the role.
- JWT `exp` is 8 hours from issue. There is no refresh flow; users are silently logged out on 401.

## Uploads

- Upload requests are streamed into memory up to 500 MB. Files larger than that are rejected with a generic error rather than a helpful message.
- The XLSX parser tries `python-calamine` first, then falls back to `openpyxl`. Hyperlink recovery **requires** openpyxl; if calamine wins and the file needs link recovery, the second load re-reads the bytes. This assumes the file bytes are cheap to re-parse (they are, but larger files will take proportionally longer).

## LLM (Anthropic)

- `ALL_KNOWLEDGE` fits comfortably in the system prompt. As it grows, we assume it will stay well under 100k tokens.
- Prompt caching is on by default in the SDK; there is no explicit cache-control on our side.
- The model id string is trusted; there is no fallback to another provider or model on error.

## Frontend

- `localStorage.ai_token` is trustworthy for the lifetime of the tab. No CSRF protection; safe because the API is Bearer-token based, not cookie-based.
- CSS custom properties (`--color-*`, `--font-data`) are always defined; components read them without a fallback.
- Leaflet is loaded via dynamic `import('leaflet')`. The map div id (`vaisala-map`) is stable across renders; if two `MapTab` instances mounted simultaneously, both would race for the same id.
