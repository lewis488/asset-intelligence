# Domain-Embedded Knowledge

UK highways engineering knowledge embedded directly in code, not in configuration or documentation. Any reviewer or AI agent modifying these files must understand the domain rationale or risk breaking validated outputs.

## SCANNER: CI Band Thresholds (UKPMS Standard)

**Location:** `services/ingestion.py:664–669`, `services/scoring.py:32–40`

```python
Green:  CI < 40
Amber:  40 ≤ CI < 100
Red:    CI ≥ 100
```

These are UKPMS (UK Pavement Management System) standard thresholds used across all UK highways authorities. They are not tunable per authority — they define the classification framework itself. `ci_green_threshold` and `ci_amber_threshold` in config only affect `scoring.py` (not the live production scorer `_score_asset()`).

## SCANNER: Red Band Definition

**Location:** `services/ingestion.py:664`, `services/scoring.py:78`, `routers/assets.py:280`

Red band = `red_pct > 0` (any 10m intervals scoring CI ≥ 100), NOT `avg_ci ≥ 100`.

Engineering rationale: a section's average CI rarely reaches 100 even when it contains structurally failed intervals. A section averaging CI = 36 across 100 intervals can have 2 intervals at CI ≥ 100 (red_pct = 2%). Using avg_ci ≥ 100 as the red threshold would classify almost no sections as red — it would systematically understate structural risk.

This convention matches WSCC reporting and UK published statistics (validated: 5.78% red matches WSCC published 5.7%).

## CVI: BV224b Thresholds

**Location:** `services/ingestion.py:382`, `services/ingestion.py:868`

```python
structural_ci ≥ 85  → structural_flagged
edge_ci       ≥ 50  → edge_flagged
wearing_course_ci ≥ 60  → wearingcourse_flagged
```

These are DfT BV224b Local Transport Performance Indicator thresholds. They define the point at which a CVI domain assessment requires intervention. Fixed nationally — not configurable per authority.

CVI CI direction: higher = worse (same as SCANNER). Both increase toward failure.

## CVI: Max-Not-Average for Domain Flags

**Location:** `services/ingestion.py:860–871`

Domain CIs use `max()` across sub-sections, not length-weighted average. Engineering rationale: BV224b methodology requires that any sub-section exceeding the threshold triggers the flag — the worst point drives intervention need. Length-weighting the CI would allow a long Green sub-section to mask a short but critical Structural sub-section.

## SCRIM: SFC=0 Exclusion

**Location:** `services/ingestion.py:973–978`

```python
sfc_valid = grp["SFC"][grp["SFC"] > 0].dropna()
```

Engineering rationale: Confirm SCANNER exports contain SFC=0 for intervals where the SCRIM vehicle did not record a reading (e.g., junctions, lane changes). SFC=0 is not actual zero skid resistance — including these rows would produce falsely low mean/min statistics and potentially trigger false safety flags.

## SCRIM: XDIF as Safety Flag

**Location:** `services/ingestion.py:981–986`

```python
safety_flagged = sections_below_il > 0
```

XDIF = measured SFC − SFCT (site-specific investigatory level). XDIF < 0 means skid resistance is below the investigatory level defined in DMRB HD28/08. Any section with XDIF < 0 requires investigation and potential remedial treatment. Even one interval below IL triggers the flag — same max-not-average rationale as CVI.

ILCT (Investigatory Level Category Type) defines the site category (e.g., motorway, roundabout, gradient, pedestrian crossing). Each category has a different SFCT threshold from the DMRB lookup table.

## SCANNER: Defect Driver Analysis (scoring.py)

**Location:** `services/scoring.py:99–141`

CI contribution proportions from the SCANNER survey drive treatment selection:

```
LPV (Longitudinal Profile Variance) dominant (> 40%)   → +15 pts — structural roughness, inlay/reconstruction
Rutting dominant (> 35%)                                → +15 pts — structural deformation, inlay/reconstruction
Cracking dominant (> 40%)                              → +12 pts — surface/structural, investigate
Texture dominant (> 50%)                               → +8 pts  — surface treatment sufficient
```

Engineering rationale: CI proportions reveal which distress mechanism drives deterioration. LPV and Rutting indicate structural failure (expensive treatment: inlay or reconstruction). Texture indicates surface failure only (cheap treatment: surface dressing). This drives 5–10× cost difference in treatment selection.

Band penetration bonuses (red_pct > 15% → +10 pts, amber_pct > 40% → +5 pts) reflect extent — a section with widespread red intervals is more urgent than one with a single bad interval.

**Note:** This logic is in `scoring.py` which is NOT the live production scorer. The live scorer (`_score_asset()`) does not implement defect driver analysis. See technical-debt.md.

## Vaisala: 18 Defect Weights (RAG-Validated)

**Location:** `services/vaisala_scoring.py:25–44`

Weights reflect engineering severity of each defect type:

| Defect | Weight | Rationale |
|--------|--------|-----------|
| Subsidence | 10 | Structural failure, safety risk, expensive |
| Severe pothole | 10 | Immediate safety risk, liability |
| Moderate pothole | 7 | Active deterioration, near-term intervention |
| Alligator cracking | 8 | Structural fatigue pattern, resurfacing trigger |
| Binder bleeding | 5 | Surface safety, skid resistance risk |
| Wheel track cracking | 6 | Structural — trafficking loads exceeded capacity |
| Severe longitudinal cracking | 6 | Structural — edge or lane break |
| Severe transverse cracking | 6 | Thermal or reflective cracking through structure |
| Defective asphalt overlay | 4 | Surface layer failure |
| Severe fretting | 4 | Aggregate loss, accelerating deterioration |
| Minor/Moderate pothole | 4/— | Safety, customer perception |
| Left/Right edge deterioration | 3 each | Edge break, progressive structural loss |
| Moderate longitudinal/transverse | 3 each | Moderate structural signal |
| Moderate fretting | 2 | Early surface degradation |
| Minor cracking types | 1 each | Early warning, no immediate intervention |

These weights were fixed through calibration against real WSCC survey data to produce the validated RAG thresholds. Weights and thresholds are coupled — changing one invalidates the other.

## Vaisala: RAG Threshold Derivation

**Location:** `services/vaisala_scoring.py:49–53`

```
Red ≥ 4.0: median score of Resurfacing-triggering sections was 5.46,
            90th percentile 3.72. Threshold set at 4.0.
Amber ≥ 1.8: separates any-treatment-needed roads from Monitor-only
              with low false-positive rate.
```

Statistical derivation against real WSCC Vaisala survey data. These are the only scoring thresholds in the codebase that are intentionally NOT env-configurable. Reason: comparability of RAG bands across surveys and authorities requires stable thresholds. Configurable thresholds would make RAG band counts meaningless for year-on-year comparison.

## Vaisala: PAS 2161 Category

**Location:** `services/vaisala_scoring.py:265`

PAS 2161 (published by BSI) defines road surface condition categories for visual assessment. Column name varies across export formats:
- XLSX: "PAS2161 Category" or "PAS 2161"
- SHP: "PAS2161" or "PAS 2161 RCM category" or "PAS 2161 RCM Category"

Alias-based matching handles this. Single hardcoded string lookup would miss one or more variants.

## Treatment Selection Engineering Basis

**Location:** `routers/assets.py:145–213`

The SCANNER-based treatment logic encodes standard UK highways treatment selection:

- `Inlay / reconstruction` at high red_pct: when >15% of section length is at structural failure threshold, patching or surface treatment is ineffective — structural intervention required.
- `Thin surfacing` for moderate amber penetration: thin AC overlay where structure is sound but surface is failing.
- `Surface dressing / micro-asphalt` for low amber: preventive surface treatment — cheapest intervention, effective only on structurally sound pavements.
- `Investigate — reactive masking condition` for Green + high reactive count: SCANNER shows Green condition but frequent potholes suggest the survey may be outdated or the condition is deteriorating rapidly between survey cycles.

## Reactive Job Filtering: Engineering Rationale

**Location:** `services/ingestion.py:1026–1033`

Only condition-relevant job types are ingested as condition signals:
- Potholes (CWAY): direct structural failure indicator
- Patching (CWAY): repeat patching = chronic deterioration
- Verge repairs / Kerb & Edge works: edge-break progression
- Covers & Gullies (CWAY): drainage failure affecting structure

Excluded: streetlighting, signs, marking, drainage maintenance, bridges, structures. These do not indicate carriageway deterioration and would dilute the reactive signal.

## EDI (Edge Deterioration Index) — B+C Roads Only

**Location:** `services/scoring.py:144–154`, `services/ingestion.py:121–122`

EDI is a SCANNER-derived measure of edge break on B and C roads. It is absent from A road SCANNER sheets (different survey protocol). The parser detects EDI column by name regardless of group (`if "EDI" in col_u`). EDI scoring contributes 0–15 pts in `scoring.py` (not in live `_score_asset()`).

## Recency Weighting in Reactive Scoring

**Location:** `services/scoring.py:157–177`

Reactive scoring looks back 12 months for job frequency and 6 months for emergency jobs. Recency-weighted because older reactive jobs have reduced relevance to current condition — a patching blitz 18 months ago may reflect a programme now complete.

In `_score_asset()` the equivalent logic uses `days_since_most_recent_defect < 90` (hardcoded 90 days) for the recency bonus. This is simpler but loses the frequency-in-window nuance of `scoring.py`.
