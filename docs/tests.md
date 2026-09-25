# Tests

## Current State: No Automated Test Suite

No `tests/` directory exists in the backend codebase. No pytest files, no fixtures, no integration tests, no unit tests were found as of the documentation date (September 2026).

## What Has Been Validated

The following assertions have been verified manually against real WSCC data, but are NOT covered by automated regression tests:

| Assertion | Value | Method of validation |
|-----------|-------|---------------------|
| WSCC A road mean CI | 36.9 (published 36.6) | Manual comparison of computed value to WSCC annual report |
| Red % of classified network | 5.78% (published 5.7%) | Manual comparison of computed value to WSCC published figure |
| Vaisala RAG Red threshold ≥ 4.0 | Evidence-derived | Statistical analysis of Resurfacing-triggering sections (median score 5.46, 90th percentile 3.72) |
| Vaisala RAG Amber threshold ≥ 1.8 | Evidence-derived | False-positive rate analysis separating treatment-needed from monitor-only |
| SCRIM SFC=0 exclusion | Correct | Manual inspection of Confirm export format documentation |

If code changes affect any of these outputs, there is no automated check to catch the regression.

## Subagent Definition (Not Executed)

`.claude/agents/test-engineer` subagent is defined in the project. Its specification states:
- Writes tests; never touches source code
- Invoked separately from main development flow

This subagent has not been used to date. No tests have been written via this mechanism.

## Priority Test Cases (Unwritten)

If a test suite is created, the following cases are highest priority:

### Scoring regression tests
1. SCANNER: section with red_pct > 0 and avg_ci < 100 must score as Red band (not Green)
2. SCANNER: section with avg_ci = 100 but red_pct = 0 must NOT score as Red band
3. Composite: SCRIM safety_flagged = True must add ≥ 20 pts to composite
4. Reactive: emergency_jobs_2hr > 0 must increase score vs zero emergency jobs

### Ingestion unit tests
5. `parse_scanner_raw()`: red_pct = count(CI ≥ 100) / total × 100 (whole %, not fraction)
6. `parse_cvi_raw()`: BV224b structural_flagged = True when any sub-section CI_STRUC ≥ 85
7. `parse_scrim_raw()`: SFC=0 rows excluded from mean_sfc calculation
8. `parse_reactive_raw()`: job type not in filter list produces filtered_out count, not error
9. `parse_network_file()`: ownership filter excludes non-WSCC features

### Vaisala scoring tests
10. `assign_rag(4.0)` == "Red", `assign_rag(3.99)` == "Amber"
11. `assign_rag(1.8)` == "Amber", `assign_rag(1.79)` == "Green"
12. Deduplication: two rows with same (section, from_m, to_m) different timestamps → only latest kept
13. Deduplication: two rows with same section but different from_m → both kept

### Percentage convention tests
14. SCANNER amber_pct stored as 4.35 (not 0.0435) when 4.35% of section is amber
15. Vaisala Excel %-formatted cell (0.90 in pandas) stored as 90.0

### Validation tests
16. Missing required column → 422 with column name in error message
17. CI values with max > 200 → warning (not error)
18. NSG refs with leading zeros → info message about normalisation

## Recommended Testing Approach

Given the numerical nature of the scoring models, property-based testing (e.g., `hypothesis`) is appropriate for edge cases:
- Score must always be in [0, max_possible] for each component
- Risk band must always be one of {Critical, High, Medium, Low}
- `rci_band` assignment must be deterministic from `red_pct` and `amber_pct`

Integration tests against a real PostgreSQL test database are preferred over mocked DB for the ingestion + scoring pipeline, because mock divergence from real SQL behaviour has caused past bugs (the OOM crash was caught only in production).
