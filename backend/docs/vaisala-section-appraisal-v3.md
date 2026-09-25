# Vaisala section maintenance and local defect review

Model `vaisala-programme-v3` separates the section maintenance decision from
local observations. It does not change the condition formula, defect weights,
fixed RAG boundaries or stored source scores. Current section views use this
correction with the active authority's numeric policy values, including when
that policy predates v3. Saved programmes remain immutable. The older routing
selector and automatic-monitoring switch continue to govern interval routing;
section monitoring is a recommendation requiring a recorded review, not an
automatic approval or completed action.

For sections with complete readings, adequate QC and consistent evidence:

- Green, combined individual defect measure below the configured acceptable
  screening limit: no section-wide intervention indicated.
- Green below maintenance appraisal triggers: monitor section condition.
- Green reaching a structural-associated, edge, localised or surface extent
  trigger: appraise maintenance for the affected extent, with site prerequisites.
- Amber/Red reaching structural-associated or edge triggers: engineer assessment.
- Other adequately evidenced Amber/Red sections: treatment appraisal.
- Missing, invalid, conflicting or inadequate evidence: validation, without
  construction candidates being inferred from incomplete observations.

Positive local pothole, subsidence, severe cracking, wheel track, alligator,
bleeding and edge observations, and Red intervals, remain separate local flags
regardless of the section action. Green and no section intervention do not clear
local defects or replace authority inspection obligations. These are provisional
screening rules, not CVI indices, national intervention thresholds, treatment
designs or a declaration that the road is safe. Weighted measures and sums can
overlap; they are not unique damaged lengths.

## Source location correction

Raw imports recognise `From meters` / `To meters` and metre variants. Dedup uses
NSG, sub-section reference where supplied, and from/to chainage. Invalid extents
are retained independently. Different WSCCNET stretches sharing NSG and chainage
must not collapse. Individual interval defect readings are retained in extras as
whole percentages; blank/invalid readings stay null. XLSX metadata retains the
defect and score aggregation choices. Most-severe values cannot reconstruct the
original 5 m averages.

Section details, map/programme assessments, AI context and exports retain local
flags. Standard XLSX includes a separate Local defect review worksheet so long
location lists are not lost to Excel's cell-length limit.

## Supplied West Sussex workbook reassessment

Source: `road_segment_interval_report__west_sussex__2026_09_21__15_15__utc.xlsx`.
Both aggregation settings are **Select most severe value**, report interval 10 m.
Reparsed before deployment: 553 sections; 10,952 intervals, all with valid
chainage. No rows were removed as duplicate passes. Every section score equals
the previous parser output; Green/Amber/Red counts remain 341/132/80.

| Section maintenance action | Count |
|---|---:|
| No intervention indicated | 5 |
| Monitor | 66 |
| Treatment appraisal | 195 |
| Engineer assessment | 163 |
| Evidence validation | 124 |

The 341 Green sections split into 5 no intervention, 66 monitor, 182 appraisal
and 88 validation; none has engineer assessment as its section action.
William Street is no section intervention, while its subsidence observations
remain at 180–190 m and 190–195.573 m on its source sub-section.

## Existing imports

Deploying the code recalculates current section actions. It cannot recover
chainage, complete-reading provenance or individual interval readings that the
old importer never stored. Re-import the original workbook to obtain those
fields; retain the existing survey and saved programmes for audit. Do not infer
missing chainage or complete valid readings from zero-filled stored values.
The counts above describe the local source reassessment, not a verified rewrite
of a production survey.
