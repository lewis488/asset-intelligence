# Vaisala evidence-led treatment candidates

Model version: `vaisala-candidates-v1` (23 September 2026).

The [action programme](vaisala-action-programme.md) supplies the client workflow,
with separate evidence-validation and engineering queues, immutable saved assessments
and recorded client decisions. All current client views use its five action categories
and active authority policy. The rules below describe the internal candidate screening
service; client zero-observation outcomes are labelled No intervention indicated by
this survey, and monitoring requires a client review decision.

## Scope

`services/vaisala_treatments.py` derives an action, evidence, conditional candidates,
prerequisites, cautions and gaps from the selected view's defect measures. These
are screening hypotheses, not diagnoses, approved designs or suitability scores.
RoadIQ+ scoring and treatment rules are outside this change.

All condition arithmetic, RAG weights and fixed Red >=4.0 / Amber >=1.8 thresholds
are unchanged. Existing stored treatment labels remain for provenance but are not
used by current Vaisala client views, exports or AI as recommendations. The old
`assign_treatment` and percentile helper remain legacy storage/import utilities;
the API's compatibility `treatment` field now contains a conditional candidate summary.

## Decision rules

| Evidence | Action / options |
|---|---|
| Any positive structural-group or alligator observation, individual structural-associated defect, or positive structural primary/secondary contribution | Investigate mechanism and depth. Conditional local deeper repair and broader strengthening/rehabilitation options; no surface-only candidates. |
| Localised group >=5% | Consider local patch repair, subject to location, depth, recurrence, drainage and utility checks. |
| Edge group >0 | Inspect support and drainage; edge repair/haunching with possible local reconstruction or drainage/verge works. |
| Dressing/micro group >=5%, no positive structural indications | Compare surface dressing, micro-surfacing and thin surfacing as conditional alternatives; group dominance does not choose between them. |
| Positive defects below screening triggers | Inspect local significance; do not automatically prescribe patching. |
| No positive observations, all expected defect readings valid, groups available, high QC, no conflicting condition score | Monitor with routine safety inspections; this does not establish structural soundness. |
| Missing/invalid defect evidence, incomplete provenance or QC below High/unknown | Inspect/validate; preserve positive investigation triggers and conditional candidates. |

The existing structural20% / alligator15% thresholds only identify legacy extent
triggers in the explanation. They never prescribe resurfacing. Local5% and
surface5% are retained legacy screening defaults, not national criteria. They
require authority/engineer validation; this release does not introduce a new
calibrated treatment matrix or a policy-configuration UI.

QC High uses the existing >=85 band. QC evaluates survey coverage/validity, not
defect diagnosis. Overlapping group percentages are never added as unique length.
The report evidence supports the framework, not these numerical thresholds.

## Missing evidence and provenance

Migration019 adds nullable `defect_evidence_complete` to sections and intervals.
New raw imports set it true only when every expected defect column has a finite
0..1 numeric reading for that interval; a section is true only if all contributing
intervals are true. It is calculated independently of the original score/group
fill-zero arithmetic. Invalid readings do not become confirmed zeros for screening.

Legacy rows and pre-scored SHP imports retain NULL: source validity is unknown.
They benefit immediately from positive-evidence screening without re-uploading,
but cannot qualify for Monitor purely from stored zeros. Re-uploading a complete
raw source can establish the new provenance; column presence alone is insufficient.
This flag is input completeness, not proof that every computer-vision detection is correct.

Partial 100m aggregates remain unknown where any interval is missing, while
`observed_defect_groups` retains known positive observations. Thus missing data
cannot suppress a structural investigation trigger or allow surface-only options.

## Scales, ranking and output

- Urban views retain section scale. Mixed views rank section/10m/100m cohorts
  separately using explicit `assessment_scope`.
- Percentiles are mid-ranks for ties, 0..100 with higher worse. Singletons and
  unscored rows have no percentile. All equal scores yield 50 when cohort size >1.
- `treatment_mode=percentile` remains accepted for old clients but never changes
  treatment candidates. The frontend calls it Relative priority.
- Lists, maps, CSV, XLSX and SHP use the same assessment engine. `action_counts`
  counts rows by next action; `top_treatments` counts each conditional candidate
  separately and can sum to more than the number of rows.
- CSV/XLSX include action, rationale, candidates, evidence, prerequisites,
  cautions, gaps, version, scale and relative rank. SHP's limited DBF fields are
  supplemented with full `treatment_assessments.json` and README in the ZIP.
- Existing map/SHP geometries are whole sections, not clipped intervals. The
  map uses the first matching scaled extent and labels that limitation. Lists
  expose every extent; the SHP sidecar retains all assessed rows, including unmatched ones.
- `narrative_section_id` maps an interval to its actual parent section. AI uses
  the whole-section assessment; it never uses an interval ID as a section ID.
  This scope distinction is visible in the panel. The Vaisala network summary
  also includes the new assessment instead of the stored legacy prescription.

## Rollout and rollback

The existing Procfile runs Alembic before starting the backend. Migration019 is
additive with no defaults/backfill, allowing old and new application versions to
coexist during deployment. No existing scores, rows or survey geometry are rewritten.
Application rollback can leave the nullable columns intact. Migration downgrade
removes only these new metadata fields and discards their provenance; it is tested
but is not part of the production rollout.

## Validation

`tests/test_vaisala_treatments.py` covers decisions, unknown source columns and
invalid readings, preserved scores, partial100m positive evidence, ties, scale
cohorts, all export formats, geometry, AI evidence, parent IDs and migration rollback.
Existing QC/geometry/ingestion/evidence-reporting tests remain regression gates.
`frontend/tests/vaisala-qc.test.mjs` verifies candidate details, evidence gaps,
unchanged candidates in rank view, and QC. Provider requests are stubbed in API
tests; tests do not claim deterministic validation of every generated narrative.
