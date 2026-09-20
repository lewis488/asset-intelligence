# Business Logic

## Product Purpose

Decision Support Tool (DST) for UK local highway authorities. Ingests condition survey data (SCANNER, CVI, SCRIM), reactive maintenance records, Vaisala survey data, and network geometry — linked by NSG reference — to produce a prioritised network intelligence list with AI-generated briefings.

Intelligence must emerge from data, not hardcoded narratives. Every insight the AI produces is derived from uploaded data using established UK highways engineering methodology.

## Data Sources and Scope

| Source | Road types | Format | Parser |
|--------|-----------|--------|--------|
| SCANNER | Classified (A, B, C) | Confirm 10m intervals or HMDIF Excel | `parse_scanner_raw()`, `parse_scanner_excel()` |
| CVI | Unclassified (U) | Confirm variable-length sections or CSV | `parse_cvi_raw()`, `parse_cvi_csv()` |
| SCRIM | Classified (A, B, C) skid | Confirm 10m intervals | `parse_scrim_raw()` |
| Reactive | All | Confirm jobs export or CSV | `parse_reactive_raw()`, `parse_reactive_csv()` |
| Network SHP | ABCD | GeoPackage or zipped SHP | `parse_network_file()` |
| Vaisala | Classified | RoadAI XLSX/CSV or pre-scored SHP | `vaisala_scoring.parse_raw_xlsx()` etc. |

## Authority Isolation

All data is authority-scoped. Every DB query filters by `authority_id`. No cross-authority data access is possible. Registering an authority creates an isolated data environment.

## NSG Reference as Primary Key

NSG reference links all datasets. Leading zeros are stripped on ingest and normalised to plain string. All join operations between survey data and network geometry use `nsg_ref`. Mismatches between NSG formats across data sources are the primary cause of low coverage scores.

## Composite Risk Scoring (Production — _score_asset)

**File:** `routers/assets.py:_score_asset()` (lines 46–276)

This is the live production scorer. It queries DB, combines all available data, and returns a scored dict. Called on every `GET /assets/` request.

Four components, all optional (score is 0 if dataset absent):

| Component | Max pts | Source table |
|-----------|---------|-------------|
| SCANNER score | 60 | scanner_raw_records |
| CVI score | 65 | cvi_raw_records |
| SCRIM score | 30 | scrim_records |
| Reactive score | 30 | reactive_aggregates |

**SCANNER component (0–60 pts):**
- `rci_band == "Red"`: ci_score = 40.0
- `rci_band == "Amber"`: ci_score = 20.0 + (avg_ci / 100.0 × 10.0)
- `rci_band == "Green"`: ci_score = max(0.0, avg_ci / 10.0)
- `scanner_score = ci_score + min(red_pct × 2.0, 20.0)`

**CVI component (0–65 pts):**
- structural: min(max_ci_structural / 85.0 × 40.0, 40.0)
- edge: min(max_ci_edge / 50.0 × 15.0, 15.0)
- wearing course: min(max_ci_wearingcourse / 60.0 × 10.0, 10.0)

**SCRIM component (0–30 pts):**
- `safety_flagged == True`: 20.0 + min(pct_below_il, 10.0)
- `safety_flagged == False`: 0.0

**Reactive component (0–30 pts):**
- job_score = min(total_jobs_raised × 2.0, 15.0)
- emergency_score = min(emergency_jobs_2hr × 3.0, 10.0)
- recency_score = 5.0 if days_since_most_recent_defect < 90 else 0.0

**Risk bands (composite score):**
- Critical: ≥ 65
- High: 40–64
- Medium: 20–39
- Low: < 20

**Score completeness:** count(datasets_present) / 4 × 100. Low completeness = low confidence in score.

**IMPORTANT — Dual Scoring Discrepancy:** A separate scoring engine exists in `services/scoring.py` (`compute_scanner_score`, `compute_cvi_score`). It uses different scales (0–100 for SCANNER, no SCRIM component) and different formulas. `_score_asset()` is what runs in production. `scoring.py` does NOT drive live scores. See technical-debt.md for full details.

## Treatment Recommendations (Production)

**File:** `routers/assets.py:_score_asset()` lines 145–213

Treatment strings and urgency labels are derived from condition data. Cost bands are unit rates in £/m² — hardcoded, not env-configurable.

**SCANNER-driven treatments:**

| Condition | Treatment | Urgency | Cost (£/m²) |
|-----------|-----------|---------|-------------|
| Red + red_pct > 15 + emergency reactive | Urgent reconstruction | Immediate | 80–150 |
| Red + red_pct > 15 | Inlay / reconstruction | This financial year | 45–80 |
| Red + red_pct ≤ 15 | Inlay (mill and fill) | This financial year | 20–45 |
| Amber + red_pct > 25 | Inlay (mill and fill) | Programme next year | 20–35 |
| Amber + red_pct > 10 | Thin surfacing | Programme next year | 12–20 |
| Amber | Surface dressing / micro-asphalt | Monitor and programme | 5–14 |
| Green + >5 reactive jobs | Investigate — reactive masking | Investigate this year | 0 |
| Green | Monitor | Routine inspection | 0 |

**CVI-driven treatments (when no SCANNER):**

| Flag | Treatment | Urgency | Cost (£/m²) |
|------|-----------|---------|-------------|
| structural_flagged | Structural repair / reconstruction | This financial year | 45–150 |
| wearingcourse_flagged | Surface dressing / micro-asphalt | Programme next year | 5–14 |
| edge_flagged | Edge treatment | Programme next year | 25–38 |
| None flagged | Monitor | Routine inspection | 0 |

**SCRIM override:** When `safety_flagged == True`, appends "+ Safety: skid resistance treatment" and forces `urgency = "Immediate"` regardless of condition treatment.

**Confidence rating:** High = 3–4 datasets, Medium = 2, Low = 0–1.

**Note:** Cost bands are unit rates only. Total cost per section (unit rate × length) is NOT calculated in the application. See technical-debt.md.

## Vaisala Business Logic

**File:** `services/vaisala_scoring.py`

Operates as a separate DST module. Vaisala scoring is NOT combined with the SCANNER/CVI/SCRIM/reactive composite.

**Scoring formula:** `interval_score = (Σ defect_proportion × weight) / Σ all_weights × 100`
`section_score = length-weighted average of interval_scores`

**RAG classification (fixed — not configurable):**
- Red: ≥ 4.0
- Amber: ≥ 1.8
- Green: < 1.8

These thresholds are evidence-derived against real WSCC survey data (`RAG_DERIVATION_NOTE` in `vaisala_scoring.py:49–53`). Changing them breaks RAG comparability across surveys. They are NOT env variables.

**Treatment decision tree** (`assign_treatment()`, lines 168–182):
- structural_pct ≥ 0.20 OR alligator_pct ≥ 0.15 → Resurfacing
- localised_pct ≥ 0.05 OR alligator_pct in [0.05, 0.15) → Patching
- dressing or micro ≥ 0.05 → Surface Dressing or Micro-surfacing (whichever dominant)
- edge_pct ≥ 0.05 → Patching
- else → Monitor / Patching

**Deduplication:** keys on `(section, from_m, to_m)` — physical stretch, not section alone. Two passes of different length/chainage do not collapse into one (`_dedup_by_latest_pass()`, line 469).

**Urban split:** always forces merge scale to "section" regardless of user selection. Documented rule from original brief.

**Percentile treatment ranks:** scale-scoped. 10m/100m/section ranks are not comparable across scales.

**Weight drift detection:** `detect_weight_drift()` compares current weights against `RAG_VALIDATED_WEIGHTS`. Any deviation is reported on upload.

## Ingestion Business Rules

- **SCANNER red_pct convention:** Red band = presence of red lengths (red_pct > 0), NOT avg_ci ≥ 100. Most sections never average ≥ 100 even if they contain red 10m intervals.
- **CI direction:** higher = worse for both SCANNER and CVI.
- **SCRIM SFC=0 exclusion:** SFC=0 means no reading was taken, not actual zero skid resistance. Zero rows are excluded from mean/min calculations.
- **SCRIM safety flag:** XDIF < 0 means measured SFC is below the investigatory level for that section type.
- **Reactive filtering:** Only condition-relevant job types ingested (potholes, patching, verge repairs, kerb/edge works, covers/gullies). Only "Works Complete" and "Work Inspected" statuses. Other job types filtered out.
- **Network ownership filter:** Only CLASS ∈ {A, B, C, D} AND OWNERSHIP == "WEST SUSSEX COUNTY COUNCIL". Other records excluded. This filter is hardcoded — other authorities require code change.

## Column Alias Matching

All parsers use alias-based column matching, never a single hardcoded string. Case-insensitive partial match.

- SCANNER Excel: `_SECTION_COL_MAP` (group × column keyword pairs, ingestion.py:25–60)
- SCANNER CSV: `_SCANNER_CSV_ALIASES` (ingestion.py:253–283)
- CVI: `_CVI_ALIASES` (ingestion.py:370–379)
- Reactive: `_REACTIVE_ALIASES` (ingestion.py:429–438)
- Vaisala: `_find_col()` with candidate lists (vaisala_scoring.py:133–140)
- Validation: `DatasetSchema.ColumnSpec.aliases` list per field

Reason: field names differ between SHP exports, XLSX exports, and Confirm exports for the same logical field (e.g., PAS 2161 appears as "PAS2161", "PAS2161 Category", "PAS 2161", "PAS 2161 RCM category").

## AI Analysis Layer

`POST /analysis/run` triggers: (1) score all assets for authority, (2) build stats dict, (3) construct LLM prompt with dataset context, (4) call Claude API, (5) persist `AnalysisRun`.

`POST /analysis/query` supports multi-turn free-text queries against the same loaded dataset.

Knowledge base (`services/knowledge.py:ALL_KNOWLEDGE`) is injected as cached system prompt content on every LLM call.

`GET /analysis/stats` returns KPI statistics without any LLM call.
