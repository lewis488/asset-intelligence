# Evidence-based reporting — stage 1

Stage 2 has superseded the Vaisala treatment/percentile limitations described below:
see [vaisala-treatment-candidates.md](vaisala-treatment-candidates.md).

Implemented 23 September 2026. This stage changes interpretation and reporting,
not the validated condition model or the treatment-selection algorithms.

## Decision boundary

AI assessments distinguish observed condition, possible mechanisms, conditional
treatment candidates and the next justified action. Visual condition cannot
establish structural capacity, layer thickness, drainage cause or residual life.
RAG describes weighted condition; the Structural tier is a defect grouping.
Neither confirms structural failure. PAS categories remain separate.

Rule-derived treatments are screening candidates requiring engineering review.
The existing percentile mode remains a relative-rank planning scenario, explicitly
labelled as such. It is not a treatment suitability model. Replacing its allocations
with priority-only ranks and building structured suitability are subsequent work.

RoadIQ+ treatment strings now identify intervention candidates as indicative. A
SCRIM flag requests skid-resistance investigation and site-risk assessment under
the authority's response policy, rather than automatically prescribing immediate
skid treatment. Score arithmetic and safety flags are unchanged. Existing other
priority labels are screening outputs, not approved works deadlines.

## AI evidence

- Shared guidance is authority-neutral. Historical WSCC findings, generic cost
  multipliers, unverified service lives and contradictory CI-to-treatment tables
  are no longer injected into prompts. Validated benchmark calculations remain
  unchanged in their existing code and analytical documentation.
- All narrative paths use common evidence rules. Shortlists cannot establish
  network-wide prevalence; trends require comparable repeat observations.
- SCANNER red percentages, SCRIM percentages below IL and Vaisala QC percentages
  are supplied as whole percentages without a second multiplication by 100.
- Vaisala defect-group values are length-weighted group measures, not shares of
  the weighted score or suitability probabilities. Individual defect proportions
  are included when available. Overlapping groups must not be summed as distinct
  affected lengths.
- Missing QC is unknown. High QC describes survey quality, not diagnosis or
  treatment certainty. RoadIQ+ dataset-count confidence is labelled dataset
  availability in the detail panel; its underlying API field is retained.
- Vaisala AI assesses the stored whole section, not a percentile allocation or
  selected interval. This scope is stated in the panel.
- Existing saved analysis runs are historical and are not rewritten. Newly
  generated assessments use the new rules; worker-local narrative caches reset
  on deployment, and cache keys also include the assembled evidence context.

## Basis and limits

The user supplied two discussion reports dated 23 September 2026:
`uk_local_authority_highway_treatment_recommendations_report.pdf` and
`vaisala_roadai_within_uk_local_authority_highway_asset_management.pdf`.
These support separating screening, investigation and appraisal; their unresolved
source markers are not treated as executable thresholds or compliance evidence.

The UKRLG Code's published overview describes locally determined service levels,
risk-based assessment, good evidence and engineering judgement:
https://www.ukroadsliaisongroup.org/en/codes.html

No new approval claims, national intervention thresholds, service lives, costs or
response deadlines are introduced. Prompt rules guide generation; they are not
a formal verification of every possible LLM response. Structured evidence
requirements and calibrated outcome evaluation remain later-stage work.

## Verification

`tests/test_evidence_reporting.py` captures outbound AI requests with a stubbed
provider: no production data or paid generation is used. It exercises percentage
units, missing QC, individual defect evidence, authority isolation and SCRIM
investigation wording, with a fixed score regression. JSONB is compiled as JSON
only for these SQLite API tests; PostgreSQL schema and operators are unchanged.

`frontend/tests/vaisala-qc.test.mjs` checks section labels, percentile scenario
labels, defect-group explanations, whole percentages and missing-data guidance.
It can run against the deployed frontend with controlled API responses.
