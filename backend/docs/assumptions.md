# Assumptions

Assumptions baked into the codebase. Each represents a decision that could break for a different authority, dataset format, or context.

## Survey Data Assumptions

### SCANNER
- Each row in a Confirm SCANNER export represents exactly 10 metres. `total_length_m = interval_count × 10` (`ingestion.py:685`). If Confirm is configured for a different interval (e.g., 5m or 20m), length calculations will be wrong.
- OFFSET values: -5 = nearside, +5 = offside, other = centre (`ingestion.py:581`). Other values produce "centre" classification silently.
- CI_VALUE = 0 is treated as valid data (not excluded). Only SFC=0 (SCRIM) is excluded as no-data.
- `SURVEY_DATE` column name is exact. `SURVEYDATE` is also handled for SCRIM but not SCANNER.
- Multi-year files are accepted — survey year is extracted from SURVEY_DATE and each year is stored separately.

### CVI
- BV224b thresholds are fixed: structural ≥ 85, edge ≥ 50, wearing course ≥ 60. These match DfT BV224b indicator. If an authority uses different investigatory levels, code must change.
- Max-per-section (not length-weighted average) triggers CVI flags. This reflects the BV224b methodology where any flagged sub-section triggers intervention need.
- `CI_OVRLL` is length-weighted for overall condition. Domain CIs use maximum.

### SCRIM
- MSSC (Mean Summer SCRIM Coefficient) is assumed to have already been calculated in the Confirm export. No seasonal adjustment is applied in code.
- SFC=0 means no reading. This is a Confirm convention. If an authority stores actual zero-skid readings, they will be silently excluded.
- XDIF < 0 is the safety flag trigger. This assumes SFCT (threshold) is correctly populated in the export.

### Vaisala
- Excel %-formatted cells: raw pandas cell value is 0–1 decimal (90% → 0.90). The ingest multiplies by 100 to store as whole percentage. If a future Vaisala export changes this convention, all percentage columns will be wrong.
- Interval length defaults to 10.0 m if the length column is absent or ≤ 0 (`vaisala_scoring.py:309`).
- "Time UTC" column is used for deduplication ordering. If this column is absent, the last-seen row per `(section, from_m, to_m)` is kept (not guaranteed to be latest).

## Network Assumptions

- Network ownership string is exactly "WEST SUSSEX COUNTY COUNCIL" (`ingestion.py:1206`). Case-sensitive match. Any other authority requires code change.
- Road classes A, B, C, D are valid (`_NETWORK_VALID_CLASSES`). Class "U" (unclassified) is excluded from network filter. Unclassified roads appear in assets table only via CVI/reactive uploads.
- GeoPackage layer named "Road_Network" is preferred; falls back to first features layer (`ingestion.py:1247`).
- Network geometry input CRS is not EPSG:4326. Code reprojects to 4326. If source is already 4326, reprojection is harmless but wastes compute.

## NSG Reference Assumptions

- NSG references may have leading zeros that need stripping (normalisation). Applied consistently on ingest.
- NSG format is numeric-based. `_is_summary_row()` uses presence of any digit to distinguish a real NSG from a summary label (`ingestion.py:159`). Non-numeric NSG formats from other authorities could produce false summary-row exclusions.
- NSG refs from Vaisala SHP may not match NSG refs from network file exactly. No automatic resolution. Coverage gaps between Vaisala and network data are expected and flagged in UI but not auto-resolved.

## Reactive Job Assumptions

- Job type name strings match WSCC Confirm convention (e.g., "Potholes | CWAY"). Other authorities will have different naming. See technical-debt.md.
- Only "Works Complete" and "Work Inspected" statuses are condition-relevant. Jobs in other statuses are excluded.
- Recency threshold: `days_since_most_recent_defect < 90` = active deterioration signal. This is a hardcoded heuristic.
- Emergency category = priority_category = 1 (Cat1: 2 Hours). `_reactive_priority_category()` parses "Cat1:" prefix. Non-standard priority naming will return None and contribute 0 emergency points.

## Scoring Assumptions

- Score completeness = 4 data types. SCRIM is counted as 1 of 4, but SCRIM data is much rarer than SCANNER/CVI/reactive. Low completeness on a SCRIM-only gap does not mean the section is poorly understood.
- `score_completeness` used to set recommendation confidence (High/Medium/Low). "Low" confidence can apply even to a well-surveyed classified road that has no reactive history.
- The 90-day recency window for reactive scoring (`days_since_most_recent_defect < 90`) is hardcoded. No seasonal adjustment.

## AI Analysis Assumptions

- `knowledge.py:ALL_KNOWLEDGE` is a complete and accurate domain knowledge base. The LLM is instructed to treat it as authoritative. Errors or omissions in this knowledge base will propagate into AI-generated outputs.
- LLM outputs are advisory. The system prompt instructs the model to "reference specific NSG references" and "explain engineering reasoning" — but no output validation confirms it has done so.
- Anthropic API availability is required for all analysis runs. No fallback or cached responses on API outage.

## Deployment Assumptions

- Railway builds from the `main` branch. Commits to other branches have no effect on production.
- `alembic upgrade head` runs on every deploy (Procfile). Migrations must be idempotent. Rolling back a bad migration requires manual Railway intervention.
- Backend memory at 8 GB is sufficient for the largest expected Vaisala XLSX (WSCC full network, ~150k rows). Larger files from other authorities may still OOM.
