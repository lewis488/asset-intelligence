# Vaisala action programme

Model `vaisala-programme-v1` extends the conditional candidate service with deterministic work queues. It requires only an existing Vaisala survey. It does not infer a construction programme, budget, safety deadline or structural diagnosis.

## Routing

Each extent receives one model action, an evidence-derived reason code, an action brief and a question to resolve. Positive structural/alligator or edge evidence (including individual defects, score contributions and partial aggregates) takes precedence over missing evidence and prompts engineer assessment. Evidence conflicts also prompt engineering review. Additional evidence-validation prerequisites remain visible.

Otherwise incomplete source validity or inadequate QC routes to evidence validation: check original readings/imagery first, then obtain targeted verification only if the gap remains. Adequate evidence reaching existing local/surface screening triggers enters treatment appraisal with conditional candidates. Below-trigger positive observations default to engineer assessment.

Complete valid zero observations with adequate QC, zero score and Green RAG produce **No intervention indicated by this survey**. Missing values, absent provenance and missing condition scores cannot establish this outcome. Existing inspection obligations continue.

**Monitor observed deterioration** requires a recorded client decision in this release. No new automatic monitoring threshold was invented. A client action can change the working queue, but the model recommendation, evidence and original model rank remain immutable and visible.

Condition lists, details, statistics, maps and exports now use the same programme assessment and active authority policy as the Action programme preview. All five model action categories remain visible even when their count is zero. Source condition scores and RAG arithmetic are unchanged. Current model recommendations are labelled separately from client decisions in saved programmes; frozen historical snapshots are not rewritten.

The **Why these actions?** breakdown shows primary routing reason counts, complete-reading/QC limitations and the range of available positive structural/alligator group measures. It explicitly explains that any positive structural-associated observation triggers assessment of the selected extent, not a diagnosis or repair of its entire length. Group measures can overlap; they are not unique damaged length. This diagnostic does not introduce new thresholds or force queues to be populated. Stored snapshots predating the breakdown may not contain it.

## Policy and invariants

The authority default policy is `vaisala-programme-default-v1`: localised threshold 5%, surface threshold 5%, QC adequacy 85%, automatic monitoring disabled. These are inherited provisional screening defaults, not national intervention criteria. Immutable authority policy versions may change screening thresholds; QC adequacy cannot weaken the existing 85 boundary. An admin creates policy versions via the survey-scoped policy endpoint. Unknown fields, non-finite percentages and unsupported automatic monitoring are rejected.

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
