# Analytical models

Formulas, thresholds, and tunable knobs.

## Vaisala DST — priority score

Location: `backend/services/vaisala_scoring.py`.

```
per_interval:
    interval_score = (defect_matrix @ weight_vec) / sum(weights) * 100

per_section:
    priority_score       = length-weighted mean of interval_score across intervals in the section
    worst_interval_score = max(interval_score) within the section
    structural_pct       = length-weighted mean of the "structural group" proportion
    localised_pct        = length-weighted mean of the "localised group" proportion
    dressing_pct         = length-weighted mean of the "dressing group" proportion
    micro_pct            = length-weighted mean of the "micro group" proportion
    alligator_pct        = length-weighted mean of the alligator column
    edge_pct             = length-weighted mean of the "edge group" proportion
```

Vectorised via NumPy: all rows scored in one matrix multiply against a pre-extracted `weight_vec`. Primary defect on an interval is `argmax(defect_matrix * weight_vec)` — the defect with the highest weighted contribution. Section-level primary/secondary defects are derived from the section-average contribution matrix.

### Defect weights (RAG-validated)

`RAG_VALIDATED_WEIGHTS` (frozen constant, `backend/services/vaisala_scoring.py`):

| Defect key | Weight |
| --- | --- |
| Alligator cracking | 8 |
| Minor longitudinal cracking | 1 |
| Moderate longitudinal cracking | 3 |
| Severe longitudinal cracking | 6 |
| Wheel track cracking | 6 |
| Minor transverse cracking | 1 |
| Moderate transverse cracking | 3 |
| Severe transverse cracking | 6 |
| Minor pothole | 4 |
| Moderate pothole | 7 |
| Severe pothole | 10 |
| Left edge deterioration | 3 |
| Right edge deterioration | 3 |
| Moderate fretting | 2 |
| Severe fretting | 4 |
| Defective asphalt overlay | 4 |
| Binder bleeding | 5 |
| Subsidence | 10 |

RAG thresholds (fixed, evidence-derived, not user-tunable):

- Red ≥ 4.0
- Amber ≥ 1.8
- Green < 1.8

### Defect groups

Used by both aggregation and the defect-pattern treatment decision tree.

- `STRUCTURAL_KEYS` — Subsidence, Severe pothole, Wheel track cracking, Severe cracking variants.
- `ALLIGATOR_KEY` — Alligator cracking (single, weight-8 tier).
- `LOCALISED_KEYS` — Minor / Moderate pothole.
- `DRESSING_KEYS` — Severe fretting, Defective asphalt overlay.
- `MICRO_KEYS` — Binder bleeding, Moderate fretting, minor/moderate cracking variants.
- `EDGE_KEYS` — Left / Right edge deterioration.

### Treatment thresholds (defect-pattern mode)

Named constants at module scope in `backend/services/vaisala_scoring.py`:

- `STRUCTURAL_THRESH` — resurfacing trigger on the structural group proportion.
- `ALLIGATOR_TIER_THRESH` — resurfacing trigger specifically on alligator cracking (higher tier).
- `LOCALISED_THRESH` — patching trigger on the localised group (and mid-tier alligator).
- `SURFACE_THRESH` — surface-work trigger on the max of dressing/micro group proportions.

### Percentile treatment mode

`PERCENTILE_TREATMENTS` list. Rows in the current view are sorted ascending by `priority_score`; rank position becomes `idx / (n - 1) * 100`. Worst-scoring row has rank 100.

| Rank ≥ | Treatment |
| --- | --- |
| 90 | Resurfacing |
| 75 | Surface Dressing |
| 50 | Micro-surfacing |
| 0 | Monitor / Patching |

Percentile mode ignores which defects are actually present; it only relies on relative severity within the current merge scale + split. Ranking is scale-scoped because raw scores at 10m, 100m, and section are not directly comparable.

## Asset composite score

Location: `backend/services/scoring.py` (helpers `_rci_band`, `_ci_score`, `_defect_driver_score`, `_edi_score`, `_reactive_score`). Every threshold and point value is a Pydantic setting in `backend/config/__init__.py`; the table below shows defaults and the environment variable that overrides each.

### CI score (SCANNER)

Threshold on `avg_ci` chooses the band:
- `CI_GREEN_THRESHOLD` (default 40) — CI below this scores in Green.
- `CI_AMBER_THRESHOLD` (default 100) — CI at or below is Amber; above is Red.

Point ceilings for each band:
- `CI_GREEN_MAX` (10)
- `CI_AMBER_MAX` (25)
- `CI_RED_MAX` (40)

Additional `min(red_pct * 2, 20)` bonus for the share of intervals already banded red.

### Defect-driver score

`DD_<driver>_THRESHOLD` and `DD_<driver>_POINTS` control each of the four drivers (LPV, Rutting, Cracking, Texture). Above-threshold intervals earn the point award. Independent bonuses:

- `DD_HIGH_RED_THRESHOLD` (0.15) → `DD_HIGH_RED_POINTS` (10)
- `DD_HIGH_AMBER_THRESHOLD` (0.40) → `DD_HIGH_AMBER_POINTS` (5)

### EDI score (B and C class only)

- < 20 → 0
- 20–35 → `EDI_LOW_POINTS` (5)
- 35–50 → `EDI_MID_POINTS` (10)
- > 50 → `EDI_HIGH_POINTS` (15)

### CVI score (unclassified roads)

- Structural CI: `min(ci / 85 * 40, 40)`
- Edge CI: `min(ci / 50 * 15, 15)`
- Wearing-course CI: `min(ci / 60 * 10, 10)`

### SCRIM score

- `safety_flagged` true → 20 + `min(pct_below_il, 10)`
- else → 0

### Reactive score

- Jobs in last `REACTIVE_JOB_LOOKBACK_MONTHS` (12) → `min(count * REACTIVE_JOB_POINTS, REACTIVE_JOB_MAX)`
- Emergencies in last `REACTIVE_EMERGENCY_LOOKBACK_MONTHS` (6) → `min(count * REACTIVE_EMERGENCY_POINTS, REACTIVE_EMERGENCY_MAX)`
- Recency bonus: +5 if the most recent defect is within 90 days.

### Risk band cut points

- `RISK_CRITICAL` (65)
- `RISK_HIGH` (40)
- `RISK_MEDIUM` (20)

## Correlation analysis (frontend)

Location: `frontend/src/pages/Vaisala.jsx`, Correlation tab helpers (module-scoped): `computeRanks`, `pearsonCorr`, `pct75`.

- `computeRanks(values)` — Spearman ranks with tie-handling (assigns average rank across a tie group).
- `pearsonCorr(xs, ys)` — Pearson product-moment correlation coefficient.
- 75th-percentile helper used for the "top quartile agreement" measure between list rankings.

Correlation is computed on the client from `allSections` payloads. Reported metrics are cross-list agreement between (List 1 Road Surface Condition, List 2 Asphalt Condition, List 3 PAS 2161, List 4 weighted score).

## QC bands

QC completeness and reliability bands are stored on `vaisala_sections` (`qc_completeness_band`, `qc_reliability_band`) but the source data does not always populate them; the `QCTab` on the frontend detects "no QC available" and hides the analysis when both columns are null across the survey. The bands are derived by a separate Vaisala QC process (upstream), not by our backend.

## Scoring version

`SCORING_VERSION` env var (default `1.0.0`) is stamped on every `RiskScore` row so old scores can be identified after a weight or threshold change. Bumping this string is a manual step; there is no auto-migration of historical rows.
