# Vaisala Action Programme Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan task by task in this session. Use `superpowers:subagent-driven-development` only if delegation is authorised. Track the checkboxes below. This is a proposed plan, not an instruction to begin implementation.

**Goal:** Turn an existing Vaisala survey into an explainable, ranked programme of next actions that a client can review, assign and export without uploading another dataset.

**Architecture:** Extend the existing deterministic treatment assessment with structured evidence flags and a separate programme service. Calculate recommendations and queue ranks from the selected survey and effective scale; save immutable programme snapshots and append-only client review events. The UI, exports and optional AI explanations consume the same programme records.

**Tech stack:** Existing FastAPI, SQLAlchemy/PostgreSQL/Alembic, Pydantic, React/Vite, pytest and Node browser tests. No new AI provider or external data dependency.

**Spec:** The product and decision specification in sections 1–7 of this document. Baseline implementation: commit `6bba04b`; read `backend/docs/vaisala-treatment-candidates.md`, `business-logic.md`, `analytical-models.md`, `technical-debt.md` and `domain-embedded.md` before execution.

**Execution record (24 September 2026):** Tasks 1–7 implemented. The detailed checkboxes below preserve the proposed workflow; the verification evidence here and in `backend/docs/vaisala-action-programme.md` records execution. The combined backend suite passed 62 tests including the disposable PostgreSQL full migration chain; final focused tests cover review fixes. Seven browser checks and the production build passed before the final recovered-map regression. Release checks follow after final review. Changes are consolidated into one verified release commit instead of publishing incomplete intermediate slices.

**Recorded decisions:** Client-reviewed actions determine current work queues and export sheets, while frozen model counts/ranks remain available. GIS exports are explicitly current previews; saved CSV/XLSX exports are the reviewed handover. Interval-only sources receive a temporary section assessment rather than disappearing. The 100,000-row core benchmark measured 14.64 seconds/420.7MB: memory target met, provisional 10-second target not met. Duplicate assessment work was removed; remaining large-preview latency is documented rather than represented as verified production performance.

## 1. Product contract

After selecting a survey, the client can open **Action programme**, see a complete reconciliation of all assessed lengths into action queues, inspect the reason and next step for each location, and export that programme. No surface inventory, traffic, costs, asset history or additional survey is required to produce it.

The programme is an evidence-led worklist, not an approved construction programme. A recommendation to obtain additional information is itself an actionable output. Worklists can include treatment appraisal, engineering assessment, targeted evidence validation, monitoring and no intervention indicated by the current observations.

One location has one primary queue and can have additional prerequisite tasks. Known structural indications must survive missing evidence; such a location remains in engineering assessment and also receives an evidence-validation task. Multiple candidate treatments never multiply the location or its length.

Client questions answered: Where? What next? Why? Where in this queue? What must the next action resolve? What happens after that check? Who has reviewed it?

## 2. Global constraints

- Vaisala DST only; no RoadIQ+ scoring, ingestion or UI changes.
- Preserve all existing condition scores, weights, Red >=4.0 and Amber >=1.8, survey deduplication and benchmarks.
- Urban split always forces merge scale to section. Combined interval views retain separate effective-scale cohorts.
- Percentiles cannot choose a treatment, action, deadline or safety category.
- Whole percentages remain whole percentages; do not add overlapping defect group percentages as unique affected area or length.
- Authority scope comes from the authenticated user and owning survey; never trust an authority ID from a request body.
- Survey time, import time and assessment time are separate. Missing survey date remains unknown.
- Existing and incomplete surveys work immediately. Unknown evidence cannot imply observed absence.
- All new screening policy parameters are versioned and authority-scoped; fixed Vaisala RAG is excluded from editable policy.
- No automatic deadlines, costs, deterioration trends, service-life estimates, safety judgements or final treatment designs from this single survey.
- Existing section/interval views and API clients remain supported. Do not rewrite stored legacy labels or surveyed data.
- Maps remain optional. A client with no network geometry must receive a complete usable table and export.

## 3. Action model and decision order

Use stable machine codes and separate client labels:

| Code | Client label | Default routing | Required next-step brief |
|---|---|---|---|
| `engineer_assessment` | Engineer assessment | Any positive structural/alligator evidence, edge deterioration, evidence conflicts, or other positive observations not eligible for treatment appraisal | Identify observed defects and location; state whether the engineer must establish depth/mechanism, edge support/drainage, or local significance. |
| `evidence_validation` | Validate evidence / further survey | Material missing/invalid measures or low/unknown QC, with no overriding positive structural/edge indication | Check original imagery/export and coverage first; if the gap cannot be resolved, obtain targeted inspection or survey of the unresolved extent. |
| `treatment_appraisal` | Treatment appraisal | Adequate evidence and existing conditional surface/localised candidates; no structural/edge override or unresolved conflict | Inspect suitability and compare the existing candidate families, retaining all prerequisites and cautions. |
| `monitor` | Monitor observed deterioration | Client-reviewed monitoring decision, or an explicitly enabled and validated authority monitoring rule | Identify the observed defect and extent to revisit; compare at the next authority-defined review. No invented interval or trend. |
| `no_action_indicated` | No intervention indicated by this survey | Complete valid readings, all observed defect evidence zero, adequate QC and no conflicting score/RAG | No additional condition-led intervention identified from these observations; continue existing inspection obligations. |

Decision order:

1. Preserve any positive structural or edge indication, including partial interval evidence: engineer assessment; add evidence-validation prerequisites if needed.
2. Conflicting score/defect evidence: engineer assessment with a specific reconciliation task. Do not silently recalculate a score.
3. Missing/invalid evidence, unknown provenance, or QC below the existing High boundary: evidence validation. Preserve any conditional candidates as blocked options, not ready works.
4. Existing surface/localised candidate trigger reached with adequate evidence: treatment appraisal.
5. Positive observations below candidate triggers: engineer assessment by default.
6. All valid observations zero, adequate QC, zero score and Green RAG: no action indicated.
7. Anything unclassified: evidence validation with a recorded reason code; never omit the row.

**Important behaviour changes:** Current zero-defect `Monitor` becomes `no_action_indicated`. Current generic `Inspect` splits into engineering assessment and evidence validation. Low-level observed defects remain conservative engineering assessments; do not invent a new automatic monitoring threshold simply to populate the Monitor queue. Monitoring is available through a documented client review decision from the first release. Automatic monitoring is an optional later policy activation after domain validation, not a prerequisite for launch.

Keep default legacy local/surface triggers at 5% and existing QC High boundary at 85 for compatibility, but expose the programme screening policy as versioned authority configuration. These are inherited screening defaults, not validated national intervention criteria. Policy can never disable structural evidence preservation or missing-evidence safeguards. V1 configuration supports these existing trigger values and an `automatic_monitoring_enabled=false` guard; reject true until a separately reviewed rule is implemented.

Do not prescribe a particular technical survey solely from a visual defect. Structural briefs ask the engineer to determine the appropriate investigation needed to establish mechanism/depth/capacity. Evidence-validation briefs distinguish missing original data from a confirmed need to collect new data.

## 4. Ranking and lengths

Do not introduce a new weighted composite priority score. Use the existing validated condition score, showing its limits.

- Partition by survey, effective scale and primary action. Display no single rank across different actions/scales.
- Engineer/appraisal queues: valid condition score descending. Equal scores share a competition rank (1, 1, 3); stable identity orders tied display rows without pretending greater engineering priority. Null scores stay visible in an explicitly unranked subgroup.
- Evidence-validation queue: show a separate validation order: known positive evidence first, then existing score descending where available; ties stable. Label this **validation order**, not condition priority. Unknown-score rows remain visible and explicitly unranked by condition.
- Monitor/no-action queues: no urgency rank. Allow location sorting and show condition values for context.
- Retain existing survey-and-scale condition percentile separately. Calculate it before action/search/pagination filters; disclose cohort size and scope. Queue ranks are also calculated before display filtering.
- Priority explanation example: “Joint condition rank 2 of 18 scored lengths in Engineer assessment, 100m view; score 3.4. Structural-associated observations require checking.” Never generate this by an LLM.
- Report assessed length, not inferred treatment length. Where interval chainage is valid, union overlaps within the same physical section and effective scale. Never sum section and child interval coverage. For section-only rows use stored section length once and label it section coverage.
- Invalid/missing chainage stays visible; report known length and count of unresolved extents separately. Do not silently use the current nominal 10m fallback as verified coverage.
- Unknown urban/rural classification must not disappear from combined views. Include it as an explicitly labelled cohort; preserve existing urban override and test totals.
- Different queues may cover overlapping source extents if the input overlaps. State that queue lengths can overlap; overall unique coverage is calculated independently. Never describe the sum of those queue totals as unique network length.

## 5. Programme record and workflow

Each record includes survey ID, stable item key, section/NSG references as supplied, road name, parent section ID, source interval IDs when available, from/to chainage, effective scale, assessed length and length basis. A section reference is not automatically a confirmed NSG link.

Decision fields: model version, policy version, evidence flags/reason codes, recommended action, recommended brief, observed evidence, QC/completeness status, existing score/RAG, condition percentile/cohort, queue rank/cohort, conditional candidates, prerequisites, limitations and next decision question.

Review fields remain separate: workflow status (`unreviewed`, `accepted`, `assigned`, `completed`, `deferred`), client action (optional), comment/reason, assignee label, reviewer identity and timestamp. A manual action change never overwrites the model recommendation or score. Changing action/status requires contributor permissions. Read-only users can view/export but cannot save reviews or policy changes.

Saved programmes freeze the source survey ID, requested/effective scales, model/policy versions, generated timestamp and assessment payload. Creation is explicit **Save programme**; viewing a survey causes no writes. A programme is a snapshot, not a live recomputation. Regeneration creates a new snapshot and never silently carries reviews to changed extents or a new survey.

Assignee is an internal text label in V1, not a notification integration. A completion records a workflow decision, not proof of repaired condition. Deferral has a mandatory reason; it never removes an item from exports. Review events use optimistic concurrency so simultaneous edits receive 409 instead of overwriting one another.

## 6. Client interface and outputs

Add **Action programme** alongside the existing condition/evidence views. Default to section scale, with existing scale/split controls and clear separate cohorts when mixed. Existing views remain available.

Top summary: assessed records, known unique coverage, unresolved extents, and count/coverage in each primary action. Five action tabs include zero-count tabs with useful explanations. A summary reconciles all records; prerequisite tasks are not additional location counts.

Table: queue rank/order, location/chainage, assessed length, next action, condition/RAG, evidence status, concise reason, review status. Filters: action, scale cohort, road/section search, RAG, evidence status and review status. Explain the difference between whole-programme totals and filtered results.

Detail: observed evidence; action brief; question to resolve; conditional candidates and prerequisites; uncertainty; review controls; source and model/policy versions. Reuse `VaisalaTreatmentAssessment` rather than duplicating candidate logic. Colour RAG and action separately and label both.

Example structural brief: “Review the recorded cracking on this extent. Establish whether deterioration is confined to the surface or involves deeper layers, and determine whether targeted investigation is needed before appraising repair.” Insert actual recorded defects/chainage; do not invent observations or diagnoses.

Example gap brief: “Defect reading completeness is unknown for this extent. Check the supplied export and available survey imagery. If the gap remains unresolved, arrange targeted verification before deciding that no intervention is indicated.”

Map: section geometry is a locator unless interval clipping is actually supported. List every programme item associated with a selected section; never colour a whole section using only the first matching interval without explanation. Unmatched items remain in the table/export.

CSV: one item per row with flattened briefs/evidence/candidates/reviews and model/policy versions. XLSX: Summary, All items, five action sheets, Methodology. Summary contains no assumed repair quantities or costs. Exports default to the whole programme; filtered export is an explicit separate choice and records filters.

Existing GeoJSON/SHP exports gain programme fields; SHP retains a full JSON sidecar and geometry-scope note. Exported content must match the UI snapshot. A printable report is not necessary for the first release; XLSX is the actionable handover.

Optional AI: summarise deterministic programme counts and leading items, citing item keys and scope. Never let AI create queue membership/rank or change action. A model outage must not stop programme generation or export. Do not use the current top-five-section summary to describe complete programme totals.

## 7. Scope boundaries and success criteria

Included: automatic queues, deterministic action briefs, explained ordering, complete coverage reconciliation, saved programme/review workflow, matching exports, existing-map integration and programme-aware narrative context.

Excluded: required surface-type input, other data integrations, budgets, procurement, annual works optimisation, route scheduling, automatic adjacent scheme merging, automatic cross-survey trends, notification systems and new geometry clipping. Adjacent assessed lengths can be selected together by a user later; V1 must preserve exact source extents rather than invent scheme boundaries.

Acceptance: a client uploads/selects Vaisala data, opens the programme, understands every location's next step, reviews/assigns it, saves and exports the same decisions. No record disappears because of missing data, missing geometry, uncertain U/R class, a null score or pagination. Programme generation requires no LLM call and no supplementary dataset.

## 8. File and interface map

Create:
- `backend/services/vaisala_programme.py`: pure routing, briefs, ranking, identity and coverage.
- `backend/schemas/vaisala_programme.py`: policy, item, snapshot, review and pagination contracts.
- `backend/models/vaisala_programme.py`: policy versions, snapshots, items and review events.
- `backend/routers/vaisala_programme.py`: scoped preview/save/read/review/export routes.
- `backend/services/vaisala_programme_exports.py`: CSV/XLSX formatting from the shared payload.
- Next Alembic revision after the actual head at implementation time; expected `020_vaisala_programme.py` if head remains 019.
- `backend/tests/test_vaisala_programme.py`, `test_vaisala_programme_api.py`, `test_vaisala_programme_exports.py`.
- `frontend/src/components/VaisalaProgramme.jsx`, `VaisalaProgrammeDetail.jsx`.
- `frontend/tests/vaisala-programme.test.mjs` and `backend/docs/vaisala-action-programme.md`.

Modify:
- `backend/services/vaisala_treatments.py`: structured evidence flags and policy-aware screening without changing scores.
- `backend/routers/vaisala.py`: shared view/provenance adapters; programme fields for existing map/export consumers.
- `backend/routers/analysis.py`, `backend/services/llm.py`: optional programme summary context only.
- `backend/main.py` and Alembic model registration: register routes/models.
- `frontend/src/pages/Vaisala.jsx`: programme entry point and source selection.
- Existing candidate/detail components as needed to prevent conflicting action labels.
- Existing Vaisala docs and regression tests.

Core signatures:

```python
def assess_treatments(row: dict, *, policy: dict | None = None) -> dict: ...
def programme_item(row: dict, *, survey_id: int, policy: dict) -> dict: ...
def build_programme(rows: list[dict], *, survey_id: int, policy: dict) -> dict: ...
def export_programme(programme: dict, *, format: str) -> bytes: ...
```

`build_programme` returns `{model_version, policy_version, survey_id, cohorts, summary, items}`. Each item includes `item_key`, `recommended_action`, `reason_codes`, `brief`, `next_question`, `prerequisite_tasks`, `evidence_status`, `queue_rank`, `queue_size`, `priority_explanation`, and the existing assessment fields. It performs no database/network calls. Add typed schemas to validate all boundaries; snippets below are contract examples rather than complete source code.

## 9. Implementation tasks

### Task 1 — Evidence contract and action routing

Files: treatment service, new programme service/schema/unit tests; existing treatment tests.

- [ ] Add fixtures for complete valid zeros; positive structural; edge; surface/localised trigger; sub-trigger positive; unknown provenance; invalid/partial evidence; score conflict.
- [ ] Write failing tests for the decision table, including this contract:

```python
def test_partial_structural_evidence_keeps_engineer_action():
    row = {"structural_pct": None, "observed_defect_groups": ["structural_pct"],
           "defect_evidence_complete": False, "assessment_scope": "100m"}
    result = programme_item(row, survey_id=1, policy=DEFAULT_POLICY)
    assert result["recommended_action"] == "engineer_assessment"
    assert "validate_evidence" in result["prerequisite_tasks"]
```

- [ ] Define `DEFAULT_POLICY` in the programme service with immutable version `vaisala-programme-default-v1`, local/surface thresholds 5, QC adequacy 85, automatic monitoring false. Validate percentages finite and 0–100; reject extra keys and changes to RAG via policy API.
- [ ] Add structured flags to `assess_treatments`: structural observed, edge observed, any positive observation, complete readings, QC adequate, evidence conflict, candidate trigger. Derive from numeric inputs and partial observations, never string-match English reasons. Keep default callers compatible.
- [ ] Implement ordered routing and reason-code-specific brief templates populated exclusively from row evidence. Existing candidates remain conditional. Make displayed action consistent wherever a programme item is present.
- [ ] Run from backend: `..\.venv-tests\Scripts\python.exe -m pytest tests/test_vaisala_programme.py tests/test_vaisala_treatments.py -q`. First run must demonstrate the new missing contract; final run passes. Review branch-boundary cases at 5 and 85.
- [ ] Commit the verified routing slice.

### Task 2 — Identities, ranking and coverage reconciliation

Files: programme service/unit tests and Vaisala view adapters.

- [ ] Add tests for tied scores, missing scores, overlapping intervals, invalid chainage, section fallback, mixed scales, unknown U/R and missing geometry.
- [ ] Build stable item keys from survey, effective scale, parent section identity and ordered source interval IDs. Do not use list index or rounded chainage alone. Retain original references; keys do not assert a cross-survey match.
- [ ] Make view adapters expose actual source IDs and source chainage/length validity. Preserve partial evidence and existing arithmetic. Explicitly include unknown U/R rows in combined programme requests without weakening urban rules.
- [ ] Implement queue partition/rank/coverage rules in section 4. Keep row totals, unique known length and unresolved extent count as separate quantities.

```python
def test_equal_scores_share_rank_and_filters_do_not_recompute_it():
    result = build_programme(three_surface_rows(scores=[4, 4, 2]),
                             survey_id=1, policy=DEFAULT_POLICY)
    assert [r["queue_rank"] for r in result["items"]] == [1, 1, 3]
    assert [r["queue_rank"] for r in result["items"] if r["queue_rank"] == 3] == [3]
```

`three_surface_rows` is a test fixture built from complete valid observations, QC 100, surface group 8, no structural/edge evidence, section scope and distinct source IDs; define it in the test file, not production.

- [ ] Test permutations produce identical identities/ranks and total record count equals sum of primary queue counts. Verify score/RAG numeric outputs remain equal to baseline fixtures.
- [ ] Run programme, QC, geometry, raw parser and treatment regression tests; commit the verified slice.

### Task 3 — Read-only programme API

Files: new router/schema/API tests, `main.py`; reusable scoped survey/view loading.

- [ ] Add `GET /vaisala/surveys/{survey_id}/programme` with scale/split/action/search/page/page_size (1–200). It authorises survey first, builds full cohorts, then filters/paginates. Return total/filtered counts, complete summary and selected items.
- [ ] Add `GET /vaisala/surveys/{survey_id}/programme/items/{item_key}` with identical scope/policy. Validate item belongs to this generated cohort; missing item returns 404.
- [ ] Reuse `_get_survey` authorisation semantics or extract a focused shared access helper; never duplicate unscoped survey queries. Explicit admin selection resolves the survey's authority for policy lookup.

```python
def test_other_authority_cannot_read_programme(api, other_authority_survey):
    response = api.get(f"/vaisala/surveys/{other_authority_survey.id}/programme")
    assert response.status_code == 404
```

- [ ] Define the `other_authority_survey` fixture using the existing test database/user pattern. Cover same-authority success, admin explicit survey access, invalid scale 400, missing interval data 422 and empty survey 200 with empty totals.
- [ ] Test pagination/search/action filters do not change baseline ranks or drop unscored records. Test no LLM/provider call occurs.
- [ ] Measure section and interval preview on synthetic 100,000-row data: record latency and peak memory, avoid N+1 database calls and duplicate full payload copies. Proposed acceptance budget: preview under 10 seconds and less than 512MB additional peak memory on the measured test host; optimise only measured failures and document hardware.
- [ ] Run API/permission/regression tests; commit.

### Task 4 — Saved programme, policy and review audit

Files: new models/migration, schema/router/API tests and model registration.

- [ ] Add additive tables: `vaisala_programme_policies` (authority, version, validated JSON, creator/time); `vaisala_programmes` (authority, survey, model/policy versions, scale/split, timestamp, frozen summary); `vaisala_programme_items` (programme, item key, frozen assessment JSON); `vaisala_programme_review_events` (item, sequence, author, timestamp, status/action/comment/assignee JSON).
- [ ] Use unique constraints `(authority_id, version)`, `(programme_id, item_key)` and `(item_id, sequence)`. Index parent/authority access. Keep FK deletions restrictive for saved audit records; do not cascade-delete saved programmes through survey deletion.
- [ ] `POST /vaisala/surveys/{survey_id}/programmes`: contributor-only; recompute server-side with pinned policy, ignore client assessment payloads, persist snapshot atomically. Accept an idempotency key unique per authority/creator to avoid duplicate saves after network retry.
- [ ] Add scoped list/read snapshot routes under `/vaisala/surveys/{survey_id}/programmes`; read returns stored decisions, never newly calculated ones.
- [ ] `POST /vaisala/programmes/{programme_id}/items/{item_key}/reviews`: contributor-only; require expected sequence and a reason for action changes/deferral. Append atomically; reject conflicts with 409. Do not rewrite frozen recommendation.
- [ ] Add authority-admin policy create/read routes; policy records immutable. Enabling unsupported automatic monitoring returns 422. Existing surveys use the versioned default until a policy exists.

```python
def test_review_does_not_rewrite_model_recommendation(saved_item, append_review):
    before = saved_item.assessment["recommended_action"]
    append_review(saved_item, action="monitor", reason="Engineer reviewed imagery", sequence=0)
    assert saved_item.assessment["recommended_action"] == before
```

Define these fixtures using the new API and test DB; verify persisted state in a fresh session, not only an in-memory ORM object. Also test cross-authority read/write/export, viewer 403, duplicate save, concurrency 409, invalid transitions and changed-scale/new-survey snapshot separation.
- [ ] Test Alembic upgrade/downgrade on disposable PostgreSQL with current schema and legacy surveys; retain SQLite coverage where supported. Existing model fields/scores remain byte-for-byte unchanged.
- [ ] Run migration/API/permission tests; commit. Do not run a destructive downgrade on production.

### Task 5 — Client programme workspace

Files: new frontend components/test, Vaisala page and candidate detail component.

- [ ] Add browser fixtures for all queues including an empty Monitor queue, unresolved extents and mixed scales. Test initial queue counts, filter persistence and unknown-score visibility.
- [ ] Implement Action programme tab, cohort selector, queue cards, paginated table and detail brief. Use existing API client/auth/loading/error conventions; cancel stale requests when survey/scale changes.
- [ ] Reuse candidate component and show model recommendation separately from any client-selected action. Include explicit Save programme and existing saved-programme selection.
- [ ] Add accept/assign/complete/defer/change-action controls for contributors; mandatory reasons, conflict refresh handling and audit trail. Viewers have no mutation controls.
- [ ] In maps, list all matching items for a section. Preserve locator geometry caveat and complete table operation without geometry.

```javascript
await page.getByRole('tab', { name: 'Action programme' }).click();
await page.getByRole('button', { name: /Engineer assessment/ }).click();
await expect(page.getByText('Establish the failure mechanism and depth')).toBeVisible();
```

Use the repository's existing browser assertion/runtime pattern when translating this interaction contract; test emitted brief text from a controlled structural fixture. Also verify no-action is never shown for missing provenance, review failures leave inputs intact and scale changes do not misassociate saved reviews.
- [ ] Run `node --test tests/vaisala-programme.test.mjs tests/vaisala-qc.test.mjs` and `npm run build` in frontend; commit.

### Task 6 — Programme exports

Files: export service, programme router/tests; existing SHP/GeoJSON adapters.

- [ ] Add preview and saved-snapshot export routes with the same authorisation as viewing. Default full programme, explicit `filtered=true` plus recorded filters for filtered exports.
- [ ] Implement CSV/XLSX layout in section 6 from shared programme records. Flatten lists consistently; include item keys, provenance, rank/cohort, brief, next question and both model/client actions.
- [ ] Escape formula-leading user-controlled spreadsheet cells, write strings as strings, and stream/download using current response patterns. Do not fetch imagery URLs during export.
- [ ] Preserve full SHP sidecar, geometry scope, unmatched records and all items per section. Geometry absence must not block CSV/XLSX.

```python
def test_export_uses_same_snapshot(snapshot, exported_rows):
    expected = {(x["item_key"], x["recommended_action"], x["queue_rank"])
                for x in snapshot["items"]}
    assert {(x["item_key"], x["recommended_action"], x["queue_rank"])
            for x in exported_rows} == expected
```

Create both fixtures through snapshot API/export parsing. Test five worksheet counts, overlapping length notes, empty queues, filtered manifests, CSV Unicode and malicious spreadsheet-leading values.
- [ ] Run export, API, geometry and existing candidate export tests; commit.

### Task 7 — Narrative consistency and documentation

Files: analysis router, LLM Vaisala context, evidence/programme docs/tests.

- [ ] Feed programme summary/cohort totals and selected item keys/briefs into an optional programme explanation. Keep current whole-section narrative visibly scoped; it must not masquerade as a selected interval's programme assessment.
- [ ] Stub provider tests and assert supplied counts are complete programme counts, prerequisites remain visible, client actions are labelled as client decisions and unknown dates do not become survey dates.
- [ ] Verify provider failure leaves deterministic worklists/export available. No calls are made merely to rank or save a programme.
- [ ] Document exact decision precedence, provisional policy defaults, monitoring limitation, rank denominator, coverage definitions, client overrides and snapshot behaviour. Update all superseded action documentation.
- [ ] Run `test_evidence_reporting.py` and programme tests; commit.

### Task 8 — Acceptance review and release

- [ ] Run end-to-end fixtures: valid clean road; low positive surface observations; surface candidate; localised candidate; structural+missing evidence; edge+low QC; pre-scored SHP with unknown provenance; interval-only/unknown U/R; no geometry; null score; empty survey.
- [ ] Confirm each assessed record has one primary queue, supported brief and traceable source. Check summaries reconcile; evidence tasks do not double-count lengths; overrides never erase recommendations.
- [ ] Run all targeted backend tests: programme unit/API/export, Vaisala treatment/QC/geometry/raw parsers, evidence reporting and permissions. Run both frontend browser suites and production build.
- [ ] Obtain read-only code and domain reviews. If scoring/ingestion files are touched, the mandated domain reviewer is required before completion. Prefer no changes to those files.
- [ ] Compare preserved benchmark/score fixtures and inspect `git diff --check`. Verify only authorised task files are staged.
- [ ] Deploy the completed vertical workflow through main after verification, following project release rules. Do not expose half-built review/snapshot endpoints through a public UI during intermediate development.
- [ ] Confirm Railway backend/frontend deployments, additive migration head and published frontend checks with controlled browser fixtures. Check scoped authenticated backend programme response if an authorised test session exists; otherwise explicitly report this live validation limit rather than fabricate a production survey.
- [ ] Application rollback leaves additive audit tables intact. Never discard review history to roll back UI code. Record commit and verification evidence.

## 10. Delivery checkpoints

1. **Decision engine:** tasks 1–2 prove routing, priorities and coverage using current Vaisala data.
2. **Usable programme:** tasks 3–6 provide the complete client worklist, review and handover workflow.
3. **Release:** tasks 7–8 align narratives/docs and verify production.

These are review checkpoints within one implementation, not invitations to start unrelated features. No task requires a client to upload surface types or additional surveys. The release is complete when the programme can be generated, understood, reviewed and exported using Vaisala alone.
