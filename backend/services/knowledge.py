"""
Structured highway engineering knowledge base.
Injected as cached system context into every LLM call.
Each constant can be updated independently as standards evolve.
"""

SCANNER_KNOWLEDGE = {
    "rci_bands": {
        "green": "CI < 40 — good condition, no intervention required",
        "amber": "CI 40–99 — deteriorating, plan maintenance",
        "red": "CI >= 100 — poor condition, prioritise for treatment",
    },
    "rci_band_classification": {
        "critical_note": (
            "A section's RCI band is determined by whether it CONTAINS red or amber lengths, "
            "NOT by whether the section-average CI (AVG_CI) exceeds a threshold. "
            "SCANNER records condition at 10m intervals. A section with even one 10m interval "
            "scoring >= 100 is classified Red, even if its overall average is 45."
        ),
        "correct_logic": {
            "Red":   "red_pct > 0  — section contains at least one 10m interval in Red band",
            "Amber": "amber_pct > 0 AND red_pct = 0  — amber lengths present, no red",
            "Green": "amber_pct = 0 AND red_pct = 0  — all 10m intervals in Green band",
        },
        "avg_ci_role": (
            "AVG_CI measures average severity/deterioration across the whole section length. "
            "It is used for severity scoring within a band, not for band classification. "
            "Classifying Red only if avg_ci >= 100 is a common error — most sections will "
            "never average 100 even if they contain significant red lengths."
        ),
        "wscc_reporting": (
            "WSCC (and DfT SDL 130-01/130-02) report condition as % of network length "
            "where individual 10m intervals fall into each band. "
            "Typical WSCC figures: A roads ~5% Red, B+C roads ~5–10% Red."
        ),
    },
    "core_parameters": {
        "RUT": {
            "name": "Max rut depth",
            "core_rci": True,
            "engineering_note": (
                "Structural deformation and drainage risk. Left and right wheel tracks. "
                ">20mm is a safety concern. Rutting-dominant CI suggests sub-base or binder course "
                "deformation — surface-only treatment will not be durable."
            ),
        },
        "LPV": {
            "name": "Longitudinal Profile Variance",
            "core_rci": True,
            "engineering_note": (
                "3m and 10m moving average variance. Ride quality and structural deflection proxy. "
                "Dominant driver on B+C roads (50.7% of WSCC BC CI). High LPV with low visual "
                "surface distress suggests fatigue cracking at base level — inlay or overlay required."
            ),
        },
        "TD": {
            "name": "Texture Depth (MPD)",
            "core_rci": True,
            "engineering_note": (
                "Mean profile depth in mm. Skid resistance proxy and water dispersal. "
                "Dominant driver on A road roundabouts and A roads generally (43.4% of WSCC A CI). "
                "<0.5mm MPD is critical — may cross SCRIM investigatory level. "
                "Texture-dominant CI is positive news: surface treatment usually sufficient."
            ),
        },
        "CRK": {
            "name": "Whole carriageway cracking",
            "core_rci": True,
            "engineering_note": (
                "% of carriageway area cracked. Water ingress and fatigue indicator. "
                "Pattern matters: alligator/block = structural fatigue, transverse = thermal/reflection cracking. "
                "Cross-reference with LPV contribution to distinguish surface from structural cracking."
            ),
        },
        "ED": {
            "name": "Edge deterioration",
            "core_rci": False,
            "engineering_note": (
                "Not a core RCI parameter — reported via separate Edge Condition Indicator (EDI). "
                "High on rural B+C. Leading indicator of structural failure on roads without kerbing. "
                "EDI >50 approaches BV224b Edge CI threshold territory."
            ),
        },
    },
    "scope": (
        "Required on classified A, B, C roads. Not required on unclassified roads. "
        "Not used on trunk roads (National Highways responsibility)."
    ),
    "survey_frequency": (
        "A roads: 100% annually (both directions over 2-year cycle). "
        "B+C: 100% over 2-year cycle. Direction alternates each year."
    ),
    "output_format": "HMDIF file. 10m interval records. RCI calculated within UKPMS from core channel parameters.",
    "pas2161_note": (
        "From 2026/27, RCI three-band system (Green/Amber/Red) replaced by five-category system "
        "under PAS:2161. LAs must use accredited suppliers. Leading authorities building "
        "PAS:2161-aligned workflows now."
    ),
}

CVI_KNOWLEDGE = {
    "purpose": (
        "Coarse Visual Inspection. Rapid driven survey for unclassified road condition assessment. "
        "Standard method since 2002 (BV224b)."
    ),
    "scope": (
        "Unclassified roads primarily. SCANNER not required on U roads. "
        "Some LAs survey U roads with SCANNER voluntarily."
    ),
    "survey_cycle": "Voluntary. Typical: 25% of network per year over 4-year cycle.",
    "three_ci_domains": {
        "structural_ci": {
            "threshold": 85,
            "defects": ["wheel track cracking", "transverse cracking", "whole carriageway cracking", "rutting", "settlement/subsidence"],
            "note": (
                "Highest threshold. Severe structural deterioration. Most critical for intervention decisions. "
                "Threshold exceeded → section flagged for BV224b reporting."
            ),
        },
        "edge_ci": {
            "threshold": 50,
            "defects": ["edge deterioration", "edge break", "edge subsidence"],
            "note": (
                "Lower threshold than structural — edge failure is early warning signal. "
                "High on rural unclassified network without kerbing. "
                "Treat early before failure progresses inward."
            ),
        },
        "wearing_course_ci": {
            "threshold": 60,
            "defects": ["fretting", "ravelling", "binder loss", "surface oxidation"],
            "note": (
                "Surface-level failure. Structure may still be sound. "
                "Relevant for surface treatment vs structural intervention decision. "
                "Surface dressing or micro-asphalt may suffice if structural CI is acceptable."
            ),
        },
    },
    "bv224b": (
        "Section flagged if ANY one CI threshold is equalled or exceeded. "
        "% of network flagged = reported condition figure to DfT."
    ),
    "dvi_note": (
        "DVI (Detailed Visual Inspection) is a walked survey. Targeted at sections flagged by CVI. "
        "Used for scheme design before treatment."
    ),
}

UKPMS_KNOWLEDGE = {
    "purpose": "UK Pavement Management System. National framework for condition assessment, network analysis, treatment prioritisation.",
    "reporting": {
        "a_roads": "Single Data List 130-01. Annual mandatory reporting to DfT.",
        "bc_roads": "Single Data List 130-02.",
        "unclassified": "Voluntary. Historically BV224b. PAS:2161 will create new framework from 2026/27.",
    },
    "pas2161": {
        "published": "September 2024",
        "mandatory_from": "2026/27",
        "change": (
            "Five categories replace three bands (Green/Amber/Red). "
            "Requires accredited suppliers for SCANNER surveys. "
            "Finer-grained DfT reporting. New deterioration modelling requirements."
        ),
        "note": (
            "Authorities currently transitioning. Leading authorities building "
            "PAS:2161-aligned workflows now to avoid disruption."
        ),
    },
    "analysis_outputs": [
        "Treatment needs analysis",
        "Residual life estimation",
        "Whole life costing",
        "Network condition summary",
        "Deterioration modelling",
    ],
}

SCRIM_KNOWLEDGE = {
    "purpose": (
        "Sideways Coefficient Routine Investigation Machine. "
        "Measures skid resistance (friction coefficient on wet road). Safety-critical survey."
    ),
    "season": "May–September only (temperature dependency). Annual on A and B roads minimum.",
    "metric": "SFC (Sideways Force Coefficient) or CSC (Corrected Skid Coefficient)",
    "important_note": (
        "Being below Investigatory Level (IL) triggers investigation, not automatic treatment. "
        "IL from DMRB HD28. Must investigate cause before committing to treatment."
    ),
    "site_categories": {
        "A_motorway_straight": {"il": 0.30, "description": "Motorway mainline, straight high-speed roads"},
        "B_dual_straight": {"il": 0.35, "description": "Dual carriageway non-event sections"},
        "C_single_straight": {"il": 0.40, "description": "General single carriageway — most common rural A/B"},
        "D_minor_junction": {"il": 0.45, "description": "Approaches to T-junctions, give-way situations"},
        "F_major_junction": {"il": 0.50, "description": "Approaches to and across major junctions, roundabout approaches"},
        "G_gradient": {"il_range": "0.45–0.55", "description": "Steep gradients >5%, varies with severity"},
        "S_bend": {"il_range": "0.45–0.55", "description": "Horizontal curves, varies with radius and speed limit"},
    },
}

DEFECT_KNOWLEDGE = {
    "pothole": {
        "dft_definition": ">=40mm deep, >=300mm wide",
        "response": "Emergency 24hr",
        "ai_note": (
            "Clusters on same NSG = structural or drainage failure, not random surface deterioration. "
            "Strongest predictor of carriageway failure when CI also low. "
            "Repeated patching cost-justifies planned intervention."
        ),
    },
    "structural_failure": {
        "response": "Emergency",
        "ai_note": (
            "Recurring structural jobs on same NSG = patch repairs masking deeper failure. "
            "Triggers structural investigation. "
            "Cross-reference with SCANNER LPV and cracking contribution."
        ),
    },
    "edge_deterioration": {
        "response": "Planned",
        "ai_note": (
            "Correlates with SCANNER ED channel and CVI Edge CI. "
            "Leading indicator — treat early before failure progresses inward. "
            "High on rural B+C roads without kerbing."
        ),
    },
    "cracking_alligator": {
        "response": "Planned",
        "ai_note": (
            "Fatigue/structural origin. Cross-reference with SCANNER CRK and LPV contribution. "
            "If LPV also high, structural intervention required — surface treatment will fail quickly."
        ),
    },
    "cracking_transverse": {
        "response": "Planned",
        "ai_note": (
            "Thermal or reflection cracking from underlying layer joints. "
            "Points to layer bond failure or sub-base movement. "
            "Surface treatment alone insufficient — need to address cause."
        ),
    },
    "drainage_failure": {
        "response": "Urgent",
        "ai_note": (
            "Root cause multiplier — water ingress accelerates all other deterioration. "
            "Must investigate and resolve drainage before any resurfacing treatment. "
            "Failure to address drainage is primary cause of premature treatment failure."
        ),
    },
    "texture_skid_loss": {
        "response": "Safety-critical",
        "ai_note": (
            "Cross-reference with SCRIM data and collision history. "
            "High-speed or junction sites = safety intervention, not just maintenance. "
            "Surface dressing or thin surfacing can restore texture."
        ),
    },
}

SURFACE_TYPES = {
    "DBM": {
        "name": "Dense Bitumen Macadam",
        "design_life_years": "20–30",
        "note": "Workhorse structural surface. Most common on B, C, U roads. Sound structure needed for thin overlay.",
    },
    "HRA": {
        "name": "Hot Rolled Asphalt",
        "design_life_years": "20–25",
        "note": "Traditional UK surface. Chipping loss = texture and skid resistance risk. Largely replaced by SMA on new works.",
    },
    "SMA": {
        "name": "Stone Mastic Asphalt",
        "design_life_years": "20–25",
        "note": "High stone content, rut-resistant. Preferred for high-stress sites (roundabouts, bus stops, junctions). Min 1.5mm texture new.",
    },
    "TSS": {
        "name": "Thin Surfacing",
        "design_life_years": "10–15",
        "note": (
            "10–30mm overlay. Failure risk if applied to structurally unsound base. "
            "Structural confirmation required (FWD deflection testing recommended)."
        ),
    },
    "SD": {
        "name": "Surface Dressing",
        "design_life_years": "7–10",
        "note": (
            "Binder + chippings. Timing critical — must only be applied to structurally sound carriageway. "
            "Applied too late leads to premature failure. Best value treatment when correctly targeted."
        ),
    },
    "CONCRETE": {
        "name": "Concrete (CBP/CRCP)",
        "design_life_years": "40+",
        "note": "Different deterioration model. Joint failure and slab cracking are key failure modes. Avoid bituminous overlay (reflective cracking).",
    },
}

TREATMENT_SELECTION = {
    "surface_dressing": {
        "ci_range": "CI 65–80 / RCI Green",
        "cost_per_m2": "£3–6",
        "condition": "Surface only deteriorated, structure sound. Seals cracks, restores texture, prevents water ingress.",
    },
    "micro_asphalt": {
        "ci_range": "CI 60–75 / RCI Green",
        "cost_per_m2": "£5–10",
        "condition": "Minor cracking, oxidation. Better than SD in urban areas. Quieter, better rideability.",
    },
    "thin_surfacing": {
        "ci_range": "CI 45–65 / RCI low Amber",
        "cost_per_m2": "£12–20",
        "condition": "Surface deteriorated, structure sound. Confirm with FWD deflection testing if uncertain.",
    },
    "mill_and_fill": {
        "ci_range": "CI 35–55 / RCI mid Amber",
        "cost_per_m2": "£20–35",
        "condition": "Surface course failed, binder course sound. Most common planned maintenance on A/B roads.",
    },
    "overlay_strengthening": {
        "ci_range": "CI 25–45 / RCI high Amber",
        "cost_per_m2": "£30–60",
        "condition": "Binder/base distress. Adds structural capacity. FWD essential to size overlay correctly.",
    },
    "full_reconstruction": {
        "ci_range": "CI <35 / RCI Red",
        "cost_per_m2": "£80–150",
        "condition": "Structural or subbase failure. Drainage MUST be addressed simultaneously or treatment will fail.",
    },
}

WSCC_NETWORK_CONTEXT = {
    "authority": "West Sussex County Council",
    "a_roads_sections": 684,
    "bc_roads_sections": 1328,
    "a_roads_length_m": 926_271,
    "bc_roads_length_m": 1_564_832,
    "a_roads_mean_ci": 36.6,
    "bc_roads_mean_ci": 31.5,
    "a_roads_defect_drivers": {
        "texture": 0.434,
        "lpv": 0.323,
        "cracking": 0.205,
        "rutting": 0.038,
    },
    "bc_roads_defect_drivers": {
        "lpv": 0.507,
        "texture": 0.261,
        "cracking": 0.174,
        "rutting": 0.055,
    },
    "key_insight": (
        "On A roads, texture depth dominates CI (43.4%) — surface treatment focus, good news for cost. "
        "On B+C roads, LPV dominates (50.7%) — structural roughness and ride quality, more expensive interventions required. "
        "Worst B+C sections show combined high rutting + high EDI, indicating structural failure with edge deterioration — "
        "full reconstruction candidates."
    ),
    "roundabout_pattern": (
        "Worst A road sections are predominantly roundabouts — texture and LPV driven, high stress sites. "
        "SMA surface recommended on all roundabout treatments. "
        "Standard thin surfacing will fail quickly under turning loads."
    ),
}

# Aggregate all knowledge into a single ordered dict for LLM injection
ALL_KNOWLEDGE = {
    "SCANNER_SURVEYS": SCANNER_KNOWLEDGE,
    "CVI_SURVEYS": CVI_KNOWLEDGE,
    "UKPMS_FRAMEWORK": UKPMS_KNOWLEDGE,
    "SCRIM_SURVEYS": SCRIM_KNOWLEDGE,
    "DEFECT_TYPES": DEFECT_KNOWLEDGE,
    "SURFACE_TYPES": SURFACE_TYPES,
    "TREATMENT_SELECTION": TREATMENT_SELECTION,
    "WSCC_NETWORK_CONTEXT": WSCC_NETWORK_CONTEXT,
}
