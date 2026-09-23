"""Authority-neutral engineering guidance for AI interpretation.

Condition calculations live in the scorers. This guidance does not prescribe
national treatment thresholds, response times, costs or authority findings.
See docs/evidence-reporting.md for scope and source provenance.
"""

ALL_KNOWLEDGE = {
    "EVIDENCE_AND_DECISIONS": {
        "observations": "Report measured condition separately from hypotheses about its cause.",
        "diagnosis": (
            "Visible defects and condition indices do not establish structural capacity, "
            "layer thickness, drainage performance or residual life. Describe possible mechanisms "
            "and the inspection or investigation needed to distinguish them."
        ),
        "treatments": (
            "Rule-derived treatment labels are indicative screening candidates, not approved designs. "
            "Percentile allocations are relative ranking scenarios, not evidence of treatment suitability. "
            "Prioritisation, treatment suitability and investigation urgency are separate decisions."
        ),
        "confidence": (
            "QC completeness and reliability describe survey coverage and validity, not diagnostic "
            "certainty. Dataset counts describe availability, not treatment confidence. Missing evidence "
            "is unknown, not evidence of good condition or structural soundness."
        ),
        "scope": (
            "Use only the current authority's supplied observations. Matching NSG alone does not prove "
            "defects coincide: check chainage, direction and date. Do not infer trends without comparable "
            "repeat observations or infer network-wide patterns from a priority shortlist."
        ),
        "appraisal": (
            "Use authority-approved costs, service lives, hierarchy and intervention policies only when "
            "supplied. Unit rates are not scheme costs or whole-life appraisals. Do not invent savings, "
            "failure dates, cost multipliers or response deadlines."
        ),
    },
    "SCANNER_AND_CVI": {
        "direction": "SCANNER and CVI condition indices increase as condition worsens.",
        "scanner_bands": (
            "SCANNER interval CI: Green <40, Amber 40 to <100, Red >=100. Section band: "
            "Red if red_pct >0; otherwise Amber if amber_pct >0; otherwise Green. "
            "A section-average CI below 100 does not rule out red lengths."
        ),
        "percentages": "red_pct, amber_pct and pct_below_il are whole percentages: 4.35 means 4.35%.",
        "rutting": "Rutting describes deformation; inspect its extent and depth and investigate the affected layers before selecting treatment.",
        "profile": "Longitudinal profile describes ride unevenness. It does not measure structural deflection or establish base failure.",
        "texture": "Texture informs surface assessment and water dispersal. It does not replace measured friction and site-risk assessment.",
        "cracking": "Crack pattern, extent and severity support hypotheses about fatigue, movement or reflection; corroboration is needed to establish cause and depth.",
        "cvi": "CVI structural, edge and wearing-course flags identify condition concerns for investigation; they do not establish a final pavement design.",
    },
    "VAISALA": {
        "rag": "Fixed RoadIQ thresholds: Red >=4.0, Amber >=1.8. These classify the weighted condition score, not confirmed structural failure or national PAS categories.",
        "groups": "Structural is a defect grouping, not a structural diagnosis. Group percentages may overlap and must not be summed as distinct affected lengths.",
        "native_scores": "Road Surface Condition and Asphalt Condition: lower means worse. Keep these distinct from higher-is-worse weighted priority scores.",
        "pas": "Retain PAS 2161 categories separately from RoadIQ RAG. A condition-reporting category or technology approval does not establish treatment suitability.",
    },
    "INVESTIGATION_AND_TREATMENT": {
        "surface": "Fretting or ageing can identify preservation candidates if inspection confirms suitable pavement and drainage conditions.",
        "structural": "Wheel-track or alligator cracking, subsidence and recurring severe defects may warrant structural investigation. Compare deeper repair or strengthening options if the mechanism is confirmed.",
        "reactive": "Repeated repairs can justify reviewing history, location, drainage and utilities. Job counts alone do not prove a cause or the economics of reconstruction.",
        "edge": "Edge distress may relate to lateral support, overrunning or water. Investigate edge and drainage conditions before selecting repair.",
        "drainage": "Where drainage contributes to deterioration, address the cause as part of the treatment appraisal.",
        "skid": "Below a SCRIM Investigatory Level requires investigation, not automatic resurfacing. Determine response and any treatment through the authority's site-risk and skid-resistance policy.",
        "safety": "Condition surveys support triage but do not replace formal safety inspections. Apply supplied authority policies; do not invent universal response times.",
    },
}
