# Asset Intelligence Platform — Claude Code Context

## What this product is
A Decision Support Tool (DST) for UK local highway authorities. Ingests condition survey data (SCANNER, CVI, SCRIM), reactive maintenance data, Vaisala survey data, and network geometry — linked by NSG reference — and uses AI to produce prioritised network intelligence and maintenance recommendations.

## What it is NOT
- Not a reporting tool with pre-written narratives
- Not a WSCC-specific tool (must work for any UK highway authority)
- Not a data visualisation dashboard only

## Core product philosophy
Intelligence must emerge from the data, not from hardcoded narratives. Every insight the AI produces must be derived from the uploaded data using established UK highways engineering methodology.

## Tech stack and local ports
Frontend: React + Vite — localhost:5173
Backend: Python + FastAPI — localhost:8001 (NOT 8000 — changed to avoid a port collision with an unrelated local project)
Database: PostgreSQL
AI: Anthropic Claude API
Primary key: NSG reference across all tables

## Deployment
Live on Railway (production): frontend at www.roadiq-dst.com, backend on its own Railway domain.
Railway builds ONLY from GitHub main branch — local code changes have zero effect on the live site until committed and pushed. Any fix is not "done" until pushed and confirmed live.
Backend memory limit is 8GB (raised from a 1GB default that caused an OOM crash during Vaisala file uploads — if a similar upload/processing crash resurfaces, check Railway memory metrics before assuming it's a code bug).
API docs (/docs) are intentionally disabled when ENVIRONMENT=production — a 404 there on the live site is expected, not a bug.

## Working rules
- One problem at a time — never compound multiple changes in one prompt
- Verify each change works before moving to the next
- Any code change must be committed and pushed to GitHub (main branch) before it affects the live Railway deployment
- NSG reference is the primary key linking all datasets
- Scoring weights must be configurable per authority, never hardcoded — EXCEPT Vaisala RAG thresholds (see below), which are deliberately fixed
- All data is authority-scoped — never cross-reference between authorities
- Red band = presence of red lengths (red_pct > 0), not avg_ci >= 100
- SCANNER CI direction: higher = worse
- CVI CI direction: higher = worse (same convention)
- red_pct, amber_pct, pct_below_il are stored as WHOLE percentages (e.g. 4.35 means 4.35%), never decimal fractions — this caused multiple scoring bugs in early development, do not reintroduce
- Vaisala percentage fields sourced from Excel %-formatted cells: raw cell value is a 0-1 decimal (90% = 0.90) — multiply by 100 to store as whole percentage, consistent with the rule above
- Column name matching for fields like PAS 2161 must be alias-based (case-insensitive partial match), not a single hardcoded string — field names differ between SHP and XLSX exports

## Vaisala-specific rules (do not "fix" these — they are intentional)
- RAG thresholds (Red >= 4.0, Amber >= 1.8) are FIXED and evidence-derived against real WSCC data — NOT an env variable, NOT user-configurable, unlike every other scoring threshold in this codebase. Changing them breaks RAG comparability across surveys.
- Deduplication of survey passes keys on (section, from_m, to_m) — the physical stretch — not section alone. Two passes of different length/from_m do not collapse into one.
- Urban split always forces merge scale to "section" regardless of what scale is selected — this is a documented rule from the original brief, not a bug.
- Percentile treatment mode ranks are scale-scoped (10m/100m/section rankings are not comparable to each other) — do not compare percentile ranks across different merge scales.

## Validated benchmarks (do not silently alter)
- WSCC A road mean CI: 36.9 (matches published 36.6)
- Red % of classified network (A/B/C): 5.78% (matches WSCC published 5.7%)
- RAG thresholds (Vaisala): Red >= 4.0, Amber >= 1.8

## Documentation
Full architecture, database schema, business logic, analytical models, assumptions, technical debt, and test coverage are documented in backend/docs/*.md — read these before making changes to scoring, ingestion, or the Vaisala module. README.md at the project root is STALE — do not treat it as current.

## Subagents (.claude/agents/)
- test-engineer — writes tests, never touches source code
- code-reviewer — read-only review against technical-debt.md and domain-embedded.md
- domain-reviewer — read-only review against business-logic.md and analytical-models.md. MUST be invoked after any edit to backend/services/scoring.py, backend/services/vaisala_scoring.py, or backend/services/ingestion.py, before considering that work complete.
