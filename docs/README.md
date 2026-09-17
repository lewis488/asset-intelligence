# Asset Intelligence — Documentation Index

Living technical documentation for the Asset Intelligence platform. Regenerated after each major change; individual sections are stand-alone.

## Sections

1. [Architecture](./architecture.md) — Runtime topology, subsystems, request lifecycle.
2. [Database](./database.md) — Schema, tables, columns, migrations.
3. [Business logic](./business-logic.md) — Domain rules for scoring, RAG banding, treatment assignment, deduplication, merge scales.
4. [Analytical models](./analytical-models.md) — Formulas, thresholds, tunable weights, correlation and QC calculations.
5. [User workflows](./workflows.md) — End-to-end paths from upload through view to export.
6. [Dependencies](./dependencies.md) — Runtime libraries, external services, environment variables.
7. [Technical debt](./technical-debt.md) — Concrete refactor and hardening opportunities.
8. [Assumptions](./assumptions.md) — Implicit invariants relied on by the code.
9. [Tests](./tests.md) — Existing coverage and coverage gaps.
10. [Domain-embedded logic](./domain-embedded.md) — Magic numbers, hard-coded thresholds, duplicated constants.

## Reference implementation

The prototype for the Vaisala DST scoring engine is `vaisala_dst_handoff/priority_dst.html` — a single-file browser tool. The production backend port preserves its scoring formula, RAG thresholds, defect-group mapping, dedup rule, 100m sub-group chunking, urban-always-section rule, and percentile-treatment mode.

## Non-goals for this doc set

- No source code duplicated inline. File-path + line references only.
- No user-facing tutorials. Content targets engineers maintaining the system.
- No release notes. See git log.
