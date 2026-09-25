# Vaisala action programme

Model `vaisala-programme-v2` supplies deterministic severity/extent work queues. It requires only an existing Vaisala survey. It does not infer a construction programme, budget, safety deadline or structural diagnosis. Condition scores and the fixed RAG thresholds are unchanged.

## Routing

Each extent receives one model action, an evidence-derived reason code, an action brief and a question to resolve. The default policy uses the following ordered routing:

1. Retained positive subsidence, severe pothole, severe longitudinal/transverse cracking, moderate pothole or binder bleeding observations require local engineer assessment even at small average extents. Positive primary/secondary contributions also count. A recorded Red worst-interval score prompts assessment rather than allowing a low section average to clear the location.
2. Unknown structural defect severity, structural/alligator extent at or above 5%, and edge extent at or above 5% (or unknown edge severity) require assessment. Group measures and individual observations both contribute. These are provisional authority assessment triggers, not proof of structural failure or repair quantities.
3. Incomplete source provenance or inadequate QC requires validation unless an earlier engineering concern takes precedence. Known positive evidence is retained.
4. Complete valid zero observations, zero score and Green RAG qualify for no intervention indicated. Positive observations additionally require all 18 individual defect readings before lower-action routing: group-only micro/localised evidence cannot exclude bleeding or moderate potholes. Inconsistent groups/details or unexplained drivers require reconciliation.
5. Existing localised/surface appraisal triggers apply to adequately evidenced observations without structural/edge concerns. Surface/local deterioration meeting an appraisal trigger alongside structural/edge observations requires engineering assessment of the mixed mechanism.
6. Only minor longitudinal/transverse cracking and moderate fretting, with a combined per-defect screening upper bound strictly below 1%, adequate evidence/QC and Green condition, may qualify for no intervention indicated. The sum is a conservative screening upper bound, not unique damaged length. Individual defect and group rounding is allowed for consistency checks.
7. Other adequately evidenced below-trigger deterioration enters Monitor. Minor potholes still require assessment of local significance below the patch-appraisal trigger. Red section condition cannot enter monitoring. Monitoring asks for a documented review owner/timing under the existing authority inspection policy; no arbitrary time interval is prescribed. Disabling automatic monitoring returns these observations to assessment.

No-action and monitoring rows carry no construction candidates. Any structural observation continues to suppress surface-only candidates, including when its next action is monitoring. Section queue membership identifies an assessment/review responsibility, not a whole-section intervention boundary. Known severe observations are not averaged away by routing, but the model cannot recover observations already lost to historical source rounding.

Missing readings or provenance never establish acceptable condition. Legacy uploads and SHP/group-only evidence may remain in validation/assessment: no backfill or presumed zeros is introduced. 10m/100m views currently lack the full retained per-defect breakdown and therefore cannot establish positive minor-only condition from group totals. Complete valid zero observations remain supported at those scales. Road class U alone never relaxes the safeguards.

Client decisions can change a working queue, but saved model recommendations, evidence and original ranks remain immutable. Saved v1 snapshots are not regenerated.

Condition lists, details, statistics, maps and exports now use the same programme assessment and active authority policy as the Action programme preview. All five model action categories remain visible even when their count is zero. Source condition scores and RAG arithmetic are unchanged. Current model recommendations are labelled separately from client decisions in saved programmes; frozen historical snapshots are not rewritten.

The **Why these actions?** breakdown shows primary routing reasons, complete-reading/QC limitations and structural/alligator group extent ranges. It distinguishes minor acceptable observations, monitoring, significant local concerns and mixed mechanisms. Groups may overlap; no quota populates queues. Historical diagnostics retain their historical interpretation.

## Policy and invariants

The authority default policy is `vaisala-programme-default-v2`, with `routing_rules=severity_extent_v2`: localised/surface appraisal 5%, structural/edge assessment 5%, acceptable minor extent strictly below 1%, QC adequacy 85%, automatic monitoring enabled. The numerical action boundaries are provisional product screening defaults requiring authority calibration; they are not CVI equivalents, national criteria or calibrated West Sussex intervention thresholds. The 5% local/surface defaults are inherited; the other bounds are explicit initial policy choices. All are configurable per authority through immutable policy versions; QC cannot fall below 85. Acceptable minor extent cannot exceed the surface-appraisal threshold. Unknown fields, invalid percentages and non-boolean monitoring flags are rejected.

Existing stored authority policies without `routing_rules` retain `legacy_v1` behaviour until a new policy is explicitly created. Both built-in default versions are reserved and selectable; v1 remains available for comparison. New policy API requests default to v2. The effective policy and routing evidence are included in assessments, exports and frozen snapshots. No schema migration or source rewrite is required. `/health` reports `vaisala_action_model` for deployment verification.

Scores, condition weights, fixed Red >=4.0 / Amber >=1.8, ingestion, deduplication and stored source data are unchanged. Interval programme rows with absent source scores are explicitly unranked and have no inferred RAG; legacy display arithmetic is untouched.

Urban extents remain section-scoped. Unknown U/R rows remain in combined views. For incomplete imports retaining intervals without parent section summaries, views derive a temporary whole-section assessment where needed; no source row is written or fabricated parent narrative ID used.

## Ranking and coverage

Condition ranks are calculated within survey, effective scale and model action before search, filtering or pagination. Scores sort descending; ties use competition ranks (1,1,3); null scores remain unranked. Evidence-validation order places known observations first, then available condition score, and is labelled separately from condition urgency. Monitoring/no-action queues have no urgency rank.

Percentiles retain their original complete survey/scale cohort and never change an action or treatment. Rank denominators are shown. Client action changes receive no new invented rank; original model priority remains available as provenance.

Coverage unions valid source chainage within physical section/sub-reference. Section-only coverage uses stored section length once. Unknown/invalid chainage is counted as unresolved rather than assigned nominal 10m coverage. Overlapping queue lengths can overlap; overall known unique coverage is calculated independently. These are assessed lengths, not treatment quantities. No geometry is needed for programme tables or spreadsheet exports.

## Snapshots and review

Preview is read-only. Explicit Save programme freezes survey, scope, model/policy versions, assessment payload and summary. A repeated save with the same user/authority idempotency key returns the existing snapshot; a changed request with that key is rejected.

Review events are append-only: status, optional client action, reason/comment, assignee label, reviewer and timestamp. Contributor permissions are required. Action changes and deferrals require reasons; assignment requires a label. Optimistic sequence checks reject concurrent edits with 409. Completion is workflow status, not proof of repaired condition. Assignee labels send no notifications.

Current queue counts use recorded client actions when present. Frozen model counts and cohort ranks remain separate. Reviews never silently transfer to another survey, scale or regenerated snapshot. Foreign keys restrict removal of source/audit records. Programme policies are authority-scoped; admins operate against the explicitly selected survey's authority.

## API and exports

- Preview: `GET /vaisala/surveys/{survey_id}/programme`, plus item and export subroutes.
- Save/list: `POST/GET /vaisala/surveys/{survey_id}/programmes`.
- Snapshot read/items/export: `/vaisala/surveys/{survey_id}/programmes/{programme_id}`.
- Append review: `POST /vaisala/programmes/{programme_id}/items/{item_key}/reviews`.
- Policy versions: `/vaisala/surveys/{survey_id}/programme/policies`.

CSV contains one row per item. XLSX contains Summary, All items, five action worksheets and Methodology. Both include model/client decisions, evidence, prerequisites, provenance and review information. Filtered export is explicit; whole-programme summary totals remain labelled as such. User-supplied formula-leading spreadsheet text is escaped.

GeoJSON exposes every programme item associated with the section. Geometry remains a section locator, not a clipped intervention boundary. Existing SHP export adds programme keys/action/rank and full `action_programme.json` alongside the treatment sidecar, including unmatched rows. These GIS additions are current previews; CSV/XLSX snapshot exports are the review handover.

Programme generation, ranking, saving and exports make no AI calls. Optional AI context receives complete deterministic section programme totals and item identifiers; the top-five examples are explicitly not complete totals. Whole-section narrative context cannot claim interval scope or invent a queue rank.

## Validation and operational limits

Regression suites cover routing, partial evidence, source validity, policy boundaries, ties, missing scores, unknown U/R and interval-only surveys, coverage, API authorisation, immutable snapshots, review concurrency, export equivalence and migrations. Browser fixtures cover queue navigation, details, saved review decisions and read-only access. Provider requests are stubbed in evidence-context tests.

A synthetic core benchmark on Windows/Python 3.11.9, Intel64 family6/model142, generated 100,000 section items in 14.64 seconds with 420.7MB additional peak working set. This met the proposed 512MB memory target but exceeded the provisional 10-second time target. It measures the pure core, not database loading, JSON response or production latency. Large survey previews may take longer; the API paginates visible rows but computes ranks from the full cohort. Duplicate legacy assessment work is skipped when building programme inputs.

Migration020 is additive. Railway applies it before backend startup. Application rollback can leave the new tables intact; do not downgrade production audit tables as part of rollback. Disposable migration tests may exercise downgrade; production review history must be preserved.
