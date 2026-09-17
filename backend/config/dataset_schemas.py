"""
Field schemas for all ingested datasets.

SHP_FIELD_MAP entries are keyed by the shapefile DBF column name as written by
priority_dst.html's exportShapefile() function and map to the DB column name on
vaisala_sections. This is the authoritative mapping used by both the ingest
router and vaisala_scoring.py.
"""

VAISALA_SCHEMA = {
    # Scored SHP export field → vaisala_sections DB column
    # Source: priority_dst.html const SHP_FIELD_MAP (verified against real export)
    "shp_field_map": {
        "SECTION":    "section_ref",
        "ROAD":       "road_name",
        "NETREF":     "net_reference",
        "URBRUR":     "urban_rural",
        "LENGTH_M":   "length_m",
        "RSC":        "road_surface_condition",
        "RSC_CLASS":  "road_surface_condition_class",
        "ASPHALT":    "asphalt_condition",
        "ASPH_CLSS":  "asphalt_condition_class",
        "PAS2161":    "pas2161_category",
        "SCORE":      "priority_score",
        "WORST_INT":  "worst_interval_score",
        "RAG":        "rag_band",
        "TREATMENT":  "treatment",
        "PRI_DEFCT":  "primary_defect",
        "PRI_CONTR":  "primary_defect_contribution",
        "SEC_DEFCT":  "secondary_defect",
        "SEC_CONTR":  "secondary_defect_contribution",
        "STRUCT_PC":  "structural_pct",
        "LOCAL_PC":   "localised_pct",
        "DRESS_PC":   "dressing_pct",
        "MICRO_PC":   "micro_pct",
        "ALLIG_PC":   "alligator_pct",
        "EDGE_PC":    "edge_pct",
        "COMPLETE":   "qc_completeness_pct",
        "COMP_BAND":  "qc_completeness_band",
        "RELIABLE":   "qc_reliability_pct",
        "REL_BAND":   "qc_reliability_band",
    },

    # DB columns that must be coerced to float on ingest (all others treated as string)
    "numeric_cols": frozenset({
        "length_m",
        "road_surface_condition",
        "asphalt_condition",
        "priority_score",
        "worst_interval_score",
        "primary_defect_contribution",
        "secondary_defect_contribution",
        "structural_pct",
        "localised_pct",
        "dressing_pct",
        "micro_pct",
        "alligator_pct",
        "edge_pct",
        "qc_completeness_pct",
        "qc_reliability_pct",
    }),

    # WSCC: section_ref holds the 8-digit zero-padded NSGNO which is the nsg_ref
    # used to look up / create the Asset row. Stroud uses SECTIONLAB — no Asset
    # matching attempted for Stroud imports (network_key != "wscc").
    "wscc_nsgno_col": "section_ref",
}
