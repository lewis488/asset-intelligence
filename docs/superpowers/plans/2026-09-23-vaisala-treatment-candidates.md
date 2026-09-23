# Vaisala treatment candidates implementation plan

**Goal:** Separate evidence-led actions from conditional treatment candidates in Vaisala DST only.

**Approved design:** The user's approved approach in this task: observed defect evidence produces an initial action, candidate families, supporting reasons, prerequisites, cautions and gaps. Percentiles indicate relative priority only. Existing screening percentages are provisional triggers, not national criteria.

**Architecture:** Add a pure assessment service over whole-percentage view rows. Enrich section and interval views on read, preserving stored survey evidence and legacy treatment fields. Use the same service in Vaisala AI context. Review identified source readings previously zero-filled: migration019 adds nullable completeness metadata without rewriting legacy evidence. Existing surveys benefit without re-uploading; legacy validity remains unknown.

**Constraints:** Preserve RAG thresholds, weights, all scores, deduplication and urban section override. Authority isolation stays at existing survey endpoints. No RoadIQ+ changes. Unknown or low-quality evidence cannot silently produce a confident monitor conclusion. Relative ranks are scale-scoped and never select a treatment.

- [x] Add failing unit/API tests for structural, localised, edge, surface, no-data, low-QC and conflicting evidence; equal scores and percentile mode must not change candidates.
- [x] Implement `services/vaisala_treatments.py`: versioned actions, candidates, prerequisites, cautions, evidence gaps and export summaries. Reuse existing legacy triggers as declared screening defaults.
- [x] Integrate read-time assessment in Vaisala views, schema, map and exports; use rank-only percentiles. Feed structured assessment to Vaisala AI and its network summary.
- [x] Render action and candidate rationale in a reusable Vaisala component. Update list/map labels and relative-rank control; remove legacy prescription labels from client views.
- [x] Verify backend API/geometry/export and frontend browser/build checks. Review domain interpretation and diff. Document limitations and rollout.

**Validation:** Unit tests exercise decisions and evidence gaps. API tests compare persisted legacy labels with newly derived results, compare modes/scales and inspect exported columns. AI tests capture the structured evidence request with a stubbed provider. Browser tests inspect candidate rationale and percentile independence using controlled API responses; no production survey changes.

- [ ] Commit/push main and confirm Railway/live UI (release verification follows the implementation commit).

