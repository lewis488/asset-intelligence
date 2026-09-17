# Database schema

PostgreSQL, managed via Alembic. All timestamps default to `now()` unless noted. Migrations live in `backend/alembic/versions/`.

## Migration timeline

| ID | File | Purpose |
| --- | --- | --- |
| 001 | `001_initial_tables.py` | Authorities, Users, Assets, ScannerRecord, CviRecord, ReactiveJob, RiskScore, AnalysisRun |
| 002 | `002_raw_confirm_tables.py` | ScannerRawRecord, CviRawRecord, ScrimRecord, ReactiveJobRecord, ReactiveAggregate, NetworkAsset |
| 003 | `003_reactive_raw_tables.py` | Reactive raw-ingest refinements |
| 004 | `004_risk_scores_treatment.py` | RiskScore treatment and cost fields |
| 005 | `005_network_assets.py` | NetworkAsset (`asset_id` FK, `road_class`, `length_m`) |
| 006 | `006_vaisala_tables.py` | VaisalaSurvey / Section / Interval, defect weight sets, RAG threshold sets |
| 007 | `007_vaisala_asset_link.py` | `VaisalaSection.asset_id` FK to `assets` |
| 008 | `008_vaisala_intervals.py` | vaisala_intervals table (raw interval storage for merge scale) |
| 009 | `009_vaisala_intervals_extras.py` | `vaisala_intervals.extras_json TEXT` for recovered hyperlinks + passthrough columns |
| 010 | `010_vaisala_network_geometry.py` | `vaisala_network_geometries` + `vaisala_network_features` (GeoJSON per section_key) |

## Core tenancy

```
authorities (id PK, name, region, created_at)
  └── users (id PK, authority_id FK, email UNIQUE, hashed_password, role, created_at)
```

Every user is scoped to an authority. Every downstream row is either directly `authority_id`-scoped or joined via a survey that is.

## Asset domain

```
assets (id PK, authority_id FK, nsg_ref indexed, road_name, parish, road_class, length_m, geometry, created_at)
  ├── scanner_records         (survey_year, avg_ci, rci_band, defect %s, band %s, CI contributions)
  ├── cvi_records             (structural/edge/wearing-course CI, flagged bools)
  ├── reactive_jobs           (job_ref, type, defect_type, date, cost_gbp, response_category)
  └── risk_scores             (composite, band, component scores, treatment, confidence, scoring_version)

raw ingest sinks:
  scanner_raw_records         UNIQUE (asset_id, survey_year, offset_direction)
  cvi_raw_records             UNIQUE (asset_id, survey_year)
  scrim_records
  reactive_job_records
  reactive_aggregates
  network_assets              (asset_id FK, road_class, length_m, geometry)
```

Cascades on `assets` → `scanner_records`, `cvi_records`, `reactive_jobs`, `risk_scores` are `cascade="all, delete-orphan"`.

## Vaisala DST domain

Weight and threshold sets — versioned so scores stay reproducible after a weight edit:

```
vaisala_defect_weight_sets       (id PK, label, is_rag_validated)
  └── vaisala_defect_weights     ((weight_set_id, defect_key) PK, weight, active)

vaisala_rag_threshold_sets       (id PK, weight_set_id FK, red_threshold=4.0,
                                  amber_threshold=1.8, derivation_note)
```

Survey and section rows:

```
vaisala_surveys                  (id PK, authority_id FK, source_filename, source_format,
                                  network_key, weight_set_id FK, threshold_set_id FK,
                                  row_count, section_count, has_weight_drift, notes JSON,
                                  imported_at)
  ├── vaisala_sections           UNIQUE (survey_id, section_ref)
  │                              — section_ref, road_name, net_reference, urban_rural,
  │                                road_class, length_m, defect_%s, priority_score,
  │                                worst_interval_score, rag_band, treatment,
  │                                primary/secondary defect + contribution, QC bands,
  │                                asset_id FK → assets (nullable, ON DELETE SET NULL)
  ├── vaisala_intervals          (survey_id, section_ref, from_m, to_m, length_m,
  │                                interval_score, defect %s, primary_defect, road_surface_condition,
  │                                asphalt_condition, pas2161_category, time_utc,
  │                                extras_json TEXT)
  │                              indexes: (survey_id), (survey_id, section_ref), (interval_score)
  └── vaisala_rag_drift_log      (survey_id, defect_key, validated_weight, actual_weight, logged_at)
```

Network geometry (client-supplied road network for map join and SHP export):

```
vaisala_network_geometries       (id PK, authority_id FK, source_filename, section_field,
                                  feature_count, crs_wkt, is_active, created_at)
  └── vaisala_network_features   (id PK, geometry_id FK, section_key, geometry_geojson TEXT)
                                 indexes: (geometry_id), (geometry_id, section_key)
```

`is_active` is toggled by the upload endpoint so only one active layer exists per authority at a time; older uploads are retained but flagged inactive.

## Notable constraints

- `vaisala_sections.uq_vaisala_section_ref` — `(survey_id, section_ref)` unique. Interval-derived 100m rows are synthesised at request time; they are **not** persisted.
- `vaisala_intervals` carries no unique key — a re-upload of the same file without prior deletion appends.
- `vaisala_surveys.notes` is JSON serialised text with keys `info_meta`, `dup_groups_resolved`, `dedup_strategy` (see `POST /vaisala/upload/raw`).
- FK deletes: `vaisala_sections.asset_id ON DELETE SET NULL`; everything else on the Vaisala side cascades from the parent survey.

## Fields consumed at request time (not columns)

The following properties appear on API responses but are not stored:

- `chunk_label` — synthesised in `_intervals_to_100m_sections` and `_interval_to_section_dict`.
- `extras` — parsed from `vaisala_intervals.extras_json` per request.
- Percentile-mode `treatment` — overrides the persisted defect-pattern treatment when `treatment_mode=percentile`.
- 100m and 10m merge scales — all rows synthesised from `vaisala_intervals` on request; only `section` scale is served directly from `vaisala_sections`.
