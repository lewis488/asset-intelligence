# Analytical Models

## SCANNER Condition Model

### Input
Confirm SCANNER export: 10m interval rows with CI_VALUE, OFFSET (nearside=-5, offside=5, centre=other), SURVEY_DATE, NSG.

### Aggregation
`services/ingestion.py:parse_scanner_raw()` (line 702) — one record per `(NSG, survey_year, offset_direction)`.

- `avg_ci`: mean CI_VALUE across all intervals for the group
- `red_pct`: `count(CI_VALUE ≥ 100) / total_intervals × 100`
- `amber_pct`: `count(40 ≤ CI_VALUE < 100) / total_intervals × 100`
- `green_pct`: `count(CI_VALUE < 40) / total_intervals × 100`
- `total_length_m`: `interval_count × 10` (each row = 10m)
- `rci_band`: Red if `red_pct > 0`, else Amber if `amber_pct > 0`, else Green

### CI Band Thresholds (UKPMS standard)
- Green: CI < 40
- Amber: 40 ≤ CI < 100
- Red: CI ≥ 100

### Key invariant
Red band is determined by presence of red lengths (red_pct > 0), NOT by avg_ci ≥ 100. A section with avg_ci = 35 can have red_pct = 2.1% (a few bad 10m intervals). Treating avg_ci ≥ 100 as the red threshold was an early implementation bug and must not be reintroduced.

### Chunked processing
Files > 10 MB use `_parse_scanner_raw_chunked()` (line 551). Maintains running per-group stats across chunks. Peak DataFrame size = `_CHUNK_ROWS` (10,000 rows), regardless of file size.

---

## CVI Condition Model

### Input
Confirm CVI export: variable-length section rows with CI_OVRLL, CI_STRUC, CI_EDGE, CI_WCRSE, SECTIONLEN, SURVEY_DATE, NSG.

### Aggregation
`services/ingestion.py:parse_cvi_raw()` (line 803) — one record per `(NSG, survey_year)`.

- `avg_ci_overall`: length-weighted average `CI_OVRLL`
- `max_ci_structural`: max `CI_STRUC` across sub-sections
- `max_ci_edge`: max `CI_EDGE`
- `max_ci_wearingcourse`: max `CI_WCRSE`

### BV224b Flags (HD28/DfT thresholds)
- `structural_flagged`: max_ci_structural ≥ 85
- `edge_flagged`: max_ci_edge ≥ 50
- `wearingcourse_flagged`: max_ci_wearingcourse ≥ 60

Flag logic uses max (not average) — any sub-section exceeding threshold triggers the flag. This reflects BV224b indicator methodology where worst-case drives intervention need.

### pct_length_*_flagged
Proportion of total section length where each domain CI exceeds the threshold.

---

## SCRIM Skid Resistance Model

### Input
Confirm SCRIM export: 10m interval rows with SFC, SFCT (threshold), XDIF (SFC − SFCT), ILCT (site category), NSG, SURVEYDATE.

### Aggregation
`services/ingestion.py:parse_scrim_raw()` (line 913) — one record per `(NSG, survey_year)`.

- `mean_sfc`: mean SFC excluding SFC=0 rows
- `min_sfc`: worst (lowest) SFC excluding SFC=0 rows
- `sections_below_il`: count of intervals with XDIF < 0
- `pct_below_il`: `sections_below_il / total_intervals × 100`
- `safety_flagged`: True if any XDIF < 0
- `worst_xdif`: most negative XDIF value (largest deficit below investigatory level)

### SFC=0 Exclusion
SFC=0 indicates no reading was taken at that interval (not actual zero skid resistance). Including zeros would bias mean/min downward. Excluded from all statistics.

### Investigatory Level
XDIF = SFC − SFCT. SFCT is the site-specific investigatory level from the ILCT lookup. XDIF < 0 means measured skid resistance is below the level requiring investigation under DMRB HD28.

---

## Composite Risk Scoring Model (Production)

**Source:** `routers/assets.py:_score_asset()` lines 46–276.

### Component weights and formulas

```
SCANNER (0–60 pts):
  rci_band == Red:   ci_score = 40.0
  rci_band == Amber: ci_score = 20.0 + (avg_ci / 100.0 × 10.0)
  rci_band == Green: ci_score = max(0.0, avg_ci / 10.0)
  scanner_score = ci_score + min(red_pct × 2.0, 20.0)

CVI (0–65 pts):
  structural = min(max_ci_structural / 85.0 × 40.0, 40.0)
  edge       = min(max_ci_edge       / 50.0 × 15.0, 15.0)
  wc         = min(max_ci_wc         / 60.0 × 10.0, 10.0)
  cvi_score  = structural + edge + wc

SCRIM (0–30 pts):
  safety_flagged: 20.0 + min(pct_below_il, 10.0)
  else:           0.0

Reactive (0–30 pts):
  job_score       = min(total_jobs_raised × 2.0, 15.0)
  emergency_score = min(emergency_jobs_2hr × 3.0, 10.0)
  recency_score   = 5.0 if days_since_most_recent_defect < 90 else 0.0
  reactive_score  = job_score + emergency_score + recency_score

composite = scanner_score + cvi_score + scrim_score + reactive_score
```

### Risk Bands
- Critical: ≥ 65
- High: 40–64
- Medium: 20–39
- Low: < 20

### Dataset interaction
SCANNER and CVI components are NOT mutually exclusive — both can contribute to composite. In practice, classified roads have SCANNER data and unclassified roads have CVI data, but the model does not enforce this distinction.

### Standalone Scoring Engine (services/scoring.py)
A separate, cleaner scoring engine exists with different formulas and scales (SCANNER: 0–100, no SCRIM component). It is not called by the production API. See technical-debt.md.

---

## Vaisala Scoring Model

**Source:** `services/vaisala_scoring.py`

### Defect weighting
18 defect types with validated weights (`RAG_VALIDATED_WEIGHTS`, line 25):

| Defect | Weight |
|--------|--------|
| Subsidence | 10 |
| Severe pothole | 10 |
| Moderate pothole | 7 |
| Alligator cracking | 8 |
| Binder bleeding | 5 |
| Wheel track cracking | 6 |
| Severe longitudinal cracking | 6 |
| Severe transverse cracking | 6 |
| Defective asphalt overlay | 4 |
| Severe fretting | 4 |
| Minor pothole | 4 |
| Left/Right edge deterioration | 3 each |
| Moderate longitudinal cracking | 3 |
| Moderate transverse cracking | 3 |
| Moderate fretting | 2 |
| Minor longitudinal cracking | 1 |
| Minor transverse cracking | 1 |

These weights are frozen. They were validated against real WSCC data to derive the RAG thresholds. Changing weights invalidates the thresholds.

### Interval scoring (vectorised)
`_aggregate_intervals()` line 245:
```
defect_matrix = [proportion values for all defect columns]
weight_vec    = [weights in same order]
interval_score = (defect_matrix @ weight_vec) / sum(weights) × 100
```

Vectorised across all rows simultaneously (numpy matrix multiply).

### Section scoring
Length-weighted average of interval scores:
```
section_score = Σ(interval_score × interval_length) / total_section_length
```

### RAG Thresholds (fixed, evidence-derived)
- Red: section_score ≥ 4.0
- Amber: section_score ≥ 1.8
- Green: section_score < 1.8

Derivation: `RAG_DERIVATION_NOTE` in `vaisala_scoring.py:49–53`:
> "Red ≥ 4.0: median score of Resurfacing-triggering sections was 5.46, 90th percentile 3.72.
> Amber ≥ 1.8: separates any-treatment-needed roads from Monitor-only with low false-positive rate.
> Derived against real WSCC survey data."

**These thresholds are not env-configurable.** Unlike every other scoring parameter in this codebase. Reason: changing them breaks RAG comparability across surveys.

### Defect group classification
Used for treatment decision tree:

| Group | Defects |
|-------|---------|
| STRUCTURAL | Subsidence, Severe pothole, Wheel track cracking, Severe longitudinal/transverse cracking |
| ALLIGATOR | Alligator cracking |
| LOCALISED | Minor pothole, Moderate pothole |
| DRESSING | Severe fretting, Defective asphalt overlay |
| MICRO | Binder bleeding, Moderate fretting, Minor/Moderate longitudinal/transverse cracking |
| EDGE | Left edge deterioration, Right edge deterioration |

### Treatment assignment
`assign_treatment()` line 168 — thresholds are proportion of section length (0.0–1.0):

```
structural ≥ 0.20 → Resurfacing
alligator  ≥ 0.15 → Resurfacing
localised  ≥ 0.05 OR alligator in [0.05, 0.15) → Patching
max(dressing, micro) ≥ 0.05 → Surface Dressing or Micro-surfacing
edge ≥ 0.05 → Patching
else → Monitor / Patching
```

### Percentile mode
`assign_treatment_percentile()` line 199 — ranks sections by score within scale scope and assigns treatment by percentile band:

| Percentile rank (within scale) | Treatment |
|-------------------------------|-----------|
| ≥ 90 | Resurfacing |
| ≥ 75 | Surface Dressing |
| ≥ 50 | Micro-surfacing |
| 0–49 | Monitor / Patching |

Ranks are scale-scoped: 10m, 100m, and section scales produce non-comparable ranks.

### QC Metrics
`qc_completeness_pct` and `qc_reliability_pct` fields exist in schema but are currently NULL on all records (set to None in `_aggregate_intervals()` lines 461–463). Not implemented.

---

## What Is Not Modelled

- **Deterioration / future condition:** No HDM-4 curves, no regression on multi-year CI data, no forward projection. Multi-year data is stored but not used for trend analysis.
- **Multi-year investment planning:** No works programme by year, no sequencing logic.
- **Budget scenario modelling:** No budget-vs-outcome comparison.
- **Total treatment cost per section:** Unit rates (£/m²) are returned but not multiplied by section length anywhere in the application.

---

## Validated Benchmarks

These values were confirmed against real WSCC published figures. They must not be silently altered by code changes.

| Metric | Value | Published reference |
|--------|-------|---------------------|
| WSCC A road mean CI | 36.9 | Published 36.6 (within rounding) |
| Red % of classified network (A/B/C) | 5.78% | Published 5.7% |
| Vaisala RAG Red threshold | ≥ 4.0 | Derived from WSCC survey data |
| Vaisala RAG Amber threshold | ≥ 1.8 | Derived from WSCC survey data |
