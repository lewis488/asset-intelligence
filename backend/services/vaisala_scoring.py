"""
Vaisala DST scoring engine — ported from priority_dst.html.

Scoring formula (from HTML):
  interval_score = (sum(defect_proportion * weight) / sum(all_weights)) * 100
  section_score  = length-weighted average of interval scores
  rag_band:  Red >= 4.0, Amber >= 1.8, Green < 1.8  (static, evidence-derived)

Defect groups and treatment decision tree match the agreed client logic
from priority_dst.html's defect-pattern treatment mode exactly.
"""
from __future__ import annotations

import io
import logging
from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd
from services.vaisala_qc import calculate_qc

logger = logging.getLogger(__name__)

# ── RAG-validated weight set (frozen — thresholds derived against these) ──────
RAG_VALIDATED_WEIGHTS: dict[str, float] = {
    "Alligator cracking": 8,
    "Minor longitudinal cracking": 1,
    "Moderate longitudinal cracking": 3,
    "Severe longitudinal cracking": 6,
    "Wheel track cracking": 6,
    "Minor transverse cracking": 1,
    "Moderate transverse cracking": 3,
    "Severe transverse cracking": 6,
    "Minor pothole": 4,
    "Moderate pothole": 7,
    "Severe pothole": 10,
    "Left edge deterioration": 3,
    "Right edge deterioration": 3,
    "Moderate fretting": 2,
    "Severe fretting": 4,
    "Defective asphalt overlay": 4,
    "Binder bleeding": 5,
    "Subsidence": 10,
}

RAG_RED_THRESHOLD = 4.0
RAG_AMBER_THRESHOLD = 1.8

RAG_DERIVATION_NOTE = (
    "Red>=4.0: median score of Resurfacing-triggering sections was 5.46, 90th percentile 3.72. "
    "Amber>=1.8: separates any-treatment-needed roads from Monitor-only with low false-positive rate. "
    "Derived against real WSCC survey data."
)

# ── Defect groups (from priority_dst.html's agreed decision tree) ─────────────
STRUCTURAL_KEYS = frozenset([
    "Subsidence", "Severe pothole", "Wheel track cracking",
    "Severe longitudinal cracking", "Severe transverse cracking",
])
ALLIGATOR_KEY = "Alligator cracking"
LOCALISED_KEYS = frozenset(["Minor pothole", "Moderate pothole"])
DRESSING_KEYS = frozenset(["Severe fretting", "Defective asphalt overlay"])
MICRO_KEYS = frozenset([
    "Binder bleeding", "Moderate fretting",
    "Minor longitudinal cracking", "Moderate longitudinal cracking",
    "Minor transverse cracking", "Moderate transverse cracking",
])
EDGE_KEYS = frozenset(["Left edge deterioration", "Right edge deterioration"])

# Default treatment thresholds (match HTML UI defaults)
STRUCTURAL_THRESH = 0.20   # 20% of length
ALLIGATOR_TIER_THRESH = 0.15
LOCALISED_THRESH = 0.05
SURFACE_THRESH = 0.05

# ── Network configs (column-name candidates per network) ─────────────────────
NETWORK_CONFIGS = {
    "stroud": {
        "label": "Gloucestershire / Stroud",
        "section_keys": ["SECTIONLAB"],
        "road_name_keys": ["NAME"],
        "netref_keys": [],
        "road_class_keys": [],
        "urbrur_keys": ["URBRUR"],
        "has_rsc": True,
        "has_urbrur": True,
    },
    "wscc": {
        "label": "West Sussex (WSCC)",
        "section_keys": ["NSGNO"],
        "road_name_keys": ["ROADNAME"],
        "netref_keys": ["WSCCNET"],
        "road_class_keys": ["CLASS"],
        "urbrur_keys": [],
        "has_rsc": False,
        "has_urbrur": False,
    },
}

# SHP export field map (output of priority_dst.html → our DB)
SHP_FIELD_MAP = {
    "SECTION": "section_ref",
    "ROAD": "road_name",
    "NETREF": "net_reference",
    "URBRUR": "urban_rural",
    "LENGTH_M": "length_m",
    "RSC": "road_surface_condition",
    "RSC_CLASS": "road_surface_condition_class",
    "ASPHALT": "asphalt_condition",
    "ASPH_CLSS": "asphalt_condition_class",
    "PAS2161": "pas2161_category",
    "SCORE": "priority_score",
    "WORST_INT": "worst_interval_score",
    "RAG": "rag_band",
    "TREATMENT": "treatment",
    "PRI_DEFCT": "primary_defect",
    "PRI_CONTR": "primary_defect_contribution",
    "SEC_DEFCT": "secondary_defect",
    "SEC_CONTR": "secondary_defect_contribution",
    "STRUCT_PC": "structural_pct",
    "LOCAL_PC": "localised_pct",
    "DRESS_PC": "dressing_pct",
    "MICRO_PC": "micro_pct",
    "ALLIG_PC": "alligator_pct",
    "EDGE_PC": "edge_pct",
    "COMPLETE": "qc_completeness_pct",
    "COMP_BAND": "qc_completeness_band",
    "RELIABLE": "qc_reliability_pct",
    "REL_BAND": "qc_reliability_band",
}


def _find_col(columns: list[str], candidates: list[str]) -> Optional[str]:
    cols_lower = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand in columns:
            return cand
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]
    return None


def _safe(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    return val


def _group_max_series(df: pd.DataFrame, keys: frozenset, col_map: dict) -> pd.Series:
    available = [col_map[k] for k in keys if col_map.get(k)]
    if not available:
        return pd.Series(0.0, index=df.index)
    return df[available].apply(pd.to_numeric, errors="coerce").fillna(0).max(axis=1)


def assign_rag(score: float) -> str:
    if score >= RAG_RED_THRESHOLD:
        return "Red"
    if score >= RAG_AMBER_THRESHOLD:
        return "Amber"
    return "Green"


# Keep underscore alias for internal use
_assign_rag = assign_rag


def assign_treatment(
    structural: float, alligator: float, localised: float,
    dressing: float, micro: float, edge: float,
) -> str:
    if structural >= STRUCTURAL_THRESH:
        return "Resurfacing"
    if alligator >= ALLIGATOR_TIER_THRESH:
        return "Resurfacing"
    if localised >= LOCALISED_THRESH or (alligator >= LOCALISED_THRESH and alligator < ALLIGATOR_TIER_THRESH):
        return "Patching"
    if max(dressing, micro) >= SURFACE_THRESH:
        return "Surface Dressing" if dressing >= micro else "Micro-surfacing"
    if edge >= LOCALISED_THRESH:
        return "Patching"
    return "Monitor / Patching"


_assign_treatment = assign_treatment


# Percentile-based treatment bands — bands mirror priority_dst.html DEFAULT_TREATMENTS.
# `min` = percentile rank (0-100) required to qualify. Sort rows ascending by score;
# rank 100 = worst-scoring row.
PERCENTILE_TREATMENTS: list[dict] = [
    {"label": "Resurfacing",       "min": 90},
    {"label": "Surface Dressing",  "min": 75},
    {"label": "Micro-surfacing",   "min": 50},
    {"label": "Monitor / Patching", "min": 0},
]


def assign_treatment_percentile(rank_pct: float) -> str:
    """Return treatment label for a percentile rank (0=lowest score, 100=highest score)."""
    for band in PERCENTILE_TREATMENTS:
        if rank_pct >= band["min"]:
            return band["label"]
    return "Monitor / Patching"


def _primary_secondary_defects(row: pd.Series, col_map: dict, weights: dict[str, float]) -> tuple:
    contribs = {}
    for defect_key, weight in weights.items():
        col = col_map.get(defect_key)
        if col is None:
            continue
        v = row.get(col, 0)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            v = 0
        contribs[defect_key] = v * weight
    ranked = sorted(contribs.items(), key=lambda x: x[1], reverse=True)
    primary = ranked[0] if ranked else (None, 0)
    secondary = ranked[1] if len(ranked) > 1 else (None, 0)
    return primary[0], primary[1], secondary[0], secondary[1]


def detect_weight_drift(weights: dict[str, float]) -> list[dict]:
    drifted = []
    for key, validated in RAG_VALIDATED_WEIGHTS.items():
        actual = weights.get(key)
        if actual is None or actual != validated:
            drifted.append({
                "defect_key": key,
                "validated_weight": validated,
                "actual_weight": actual if actual is not None else 0,
            })
    return drifted


def _build_col_map(columns: list[str]) -> dict[str, str]:
    col_map = {}
    for defect_key in RAG_VALIDATED_WEIGHTS:
        found = _find_col(columns, [defect_key])
        if found:
            col_map[defect_key] = found
    return col_map


def _aggregate_intervals(df: pd.DataFrame, network_key: str, weights: dict[str, float]) -> tuple[list[dict], list[dict]]:
    """Return (sections, intervals) — both aggregated and raw interval records."""
    cfg = NETWORK_CONFIGS.get(network_key, NETWORK_CONFIGS["stroud"])
    cols = df.columns.tolist()

    section_col = _find_col(cols, cfg["section_keys"])
    if not section_col and network_key == "wscc":
        section_col = _find_col(cols, ["WSCCNET"])
    if not section_col:
        raise ValueError(f"Cannot find section reference column for network '{network_key}'. Tried: {cfg['section_keys']}")

    road_col      = _find_col(cols, cfg["road_name_keys"])
    netref_col    = _find_col(cols, cfg["netref_keys"]) if cfg["netref_keys"] else None
    urbrur_col    = _find_col(cols, cfg["urbrur_keys"]) if cfg["urbrur_keys"] else None
    road_class_col= _find_col(cols, cfg["road_class_keys"]) if cfg["road_class_keys"] else None
    length_col    = _find_col(cols, ["Length", "LENGTH", "length_m", "LENGTH_M", "Interval Length"])
    rsc_col       = _find_col(cols, ["RSC_COND", "Road surface condition", "Road Surface Condition", "RSC"])
    rsc_class_col = _find_col(cols, ["RSC_CLASS", "Road surface condition class"])
    asphalt_col   = _find_col(cols, ["ASPHALT", "Asphalt condition", "Asphalt Condition"])
    asphalt_class_col = _find_col(cols, ["ASPH_CLSS", "Asphalt condition class"])
    pas_col       = _find_col(cols, ["PAS2161", "PAS2161 Category", "PAS 2161", "PAS 2161 RCM category", "PAS 2161 RCM Category"])
    from_col      = _find_col(cols, ["Chainage Start", "ChaStart", "From", "FROM", "StartCH", "STARTM", "Start", "from_m"])
    to_col        = _find_col(cols, ["Chainage End", "ChaEnd", "To", "TO", "EndCH", "ENDM", "End", "to_m"])
    time_col      = _find_col(cols, ["Time UTC", "Time (UTC)", "TIME_UTC", "Date Time", "DateTime", "Timestamp"])

    col_map = _build_col_map(cols)

    # ── Vectorise scoring across all rows at once ─────────────────────────────
    available = [(k, col_map[k]) for k in weights if col_map.get(k)]
    total_weight = sum(weights.values())
    defect_key_list = [k for k, _ in available]

    if available and total_weight > 0:
        defect_matrix = np.column_stack([
            pd.to_numeric(df[col], errors="coerce").fillna(0).values
            for _, col in available
        ])
        weight_vec = np.array([weights[k] for k, _ in available])
        df = df.copy()
        df["_score"] = (defect_matrix @ weight_vec) / total_weight * 100

        # Per-interval primary defect (vectorised argmax)
        contrib_matrix = defect_matrix * weight_vec
        primary_indices = np.argmax(contrib_matrix, axis=1)
        primary_contribs = contrib_matrix[np.arange(len(df)), primary_indices]
        df["_pri_defect"] = [defect_key_list[i] for i in primary_indices]
        df["_pri_contrib"] = primary_contribs
    else:
        df = df.copy()
        df["_score"] = 0.0
        df["_pri_defect"] = None
        df["_pri_contrib"] = 0.0

    # Group proportions (vectorised column-max)
    df["_structural"] = _group_max_series(df, STRUCTURAL_KEYS, col_map)
    df["_localised"]  = _group_max_series(df, LOCALISED_KEYS, col_map)
    df["_dressing"]   = _group_max_series(df, DRESSING_KEYS, col_map)
    df["_micro"]      = _group_max_series(df, MICRO_KEYS, col_map)
    df["_edge"]       = _group_max_series(df, EDGE_KEYS, col_map)
    allig_col = col_map.get(ALLIGATOR_KEY)
    df["_alligator"]  = pd.to_numeric(df[allig_col], errors="coerce").fillna(0) if allig_col else 0.0

    # Length column
    df["_len"] = pd.to_numeric(df[length_col], errors="coerce").fillna(10.0) if length_col else 10.0
    df.loc[df["_len"] <= 0, "_len"] = 10.0

    # ── Collect per-interval records (pre-extracted arrays for speed) ─────────
    n = len(df)
    sec_refs   = df[section_col].astype(str).values
    road_names = df[road_col].values if road_col else np.full(n, None, dtype=object)
    net_refs   = df[netref_col].values if netref_col else np.full(n, None, dtype=object)
    urbrur_v   = df[urbrur_col].values if urbrur_col else np.full(n, None, dtype=object)
    road_cls_v = df[road_class_col].values if road_class_col else np.full(n, None, dtype=object)
    from_vals  = pd.to_numeric(df[from_col], errors="coerce").values if from_col else np.full(n, np.nan)
    to_vals    = pd.to_numeric(df[to_col],   errors="coerce").values if to_col   else np.full(n, np.nan)
    rsc_vals   = pd.to_numeric(df[rsc_col], errors="coerce").values if rsc_col else np.full(n, np.nan)
    rsc_cls_v  = df[rsc_class_col].values if rsc_class_col else np.full(n, None, dtype=object)
    asph_vals  = pd.to_numeric(df[asphalt_col], errors="coerce").values if asphalt_col else np.full(n, np.nan)
    asph_cls_v = df[asphalt_class_col].values if asphalt_class_col else np.full(n, None, dtype=object)
    pas_vals_a = df[pas_col].astype(str).values if pas_col else np.full(n, None, dtype=object)
    time_vals  = df[time_col].astype(str).values if time_col else np.full(n, None, dtype=object)
    extras_a   = df[_EXTRAS_COL].values if _EXTRAS_COL in df.columns else np.full(n, "", dtype=object)
    scores     = df["_score"].values
    struct_a   = df["_structural"].values
    local_a    = df["_localised"].values
    dress_a    = df["_dressing"].values
    micro_a    = df["_micro"].values
    allig_a    = df["_alligator"].values
    edge_a     = df["_edge"].values
    len_a      = df["_len"].values
    pri_def_a  = df["_pri_defect"].values
    pri_con_a  = df["_pri_contrib"].values

    def _flt(v):
        return None if (v is None or (isinstance(v, float) and np.isnan(v))) else float(v)
    def _str(v):
        s = str(v) if v is not None else None
        return None if s in ("None", "nan", "") else s

    raw_intervals = []
    for i in range(n):
        ref = sec_refs[i]
        if not str(ref).strip() or ref == "nan":
            continue
        raw_intervals.append({
            "section_ref": ref,
            "road_name":   _str(road_names[i]),
            "net_reference": _str(net_refs[i]),
            "urban_rural": _str(urbrur_v[i]),
            "road_class":  _str(road_cls_v[i]),
            "from_m":      _flt(from_vals[i]),
            "to_m":        _flt(to_vals[i]),
            "length_m":    float(len_a[i]),
            "interval_score": round(float(scores[i]), 4),
            "structural":  round(float(struct_a[i]), 4),
            "localised":   round(float(local_a[i]), 4),
            "dressing":    round(float(dress_a[i]), 4),
            "micro":       round(float(micro_a[i]), 4),
            "alligator":   round(float(allig_a[i]), 4),
            "edge":        round(float(edge_a[i]), 4),
            "primary_defect": _str(pri_def_a[i]),
            "primary_defect_contribution": round(float(pri_con_a[i]), 4) if pri_con_a[i] else None,
            "road_surface_condition":       _flt(rsc_vals[i]),
            "road_surface_condition_class": _str(rsc_cls_v[i]),
            "asphalt_condition":            _flt(asph_vals[i]),
            "asphalt_condition_class":      _str(asph_cls_v[i]),
            "pas2161_category":             _str(pas_vals_a[i]) if pas_col else None,
            "time_utc":                     _str(time_vals[i]),
            "extras_json":                  extras_a[i] or None,
        })

    # Per-defect columns for primary/secondary detection
    defect_avgs = {k: col_map[k] for k in col_map}

    sections = []
    for section_ref, grp in df.groupby(section_col, sort=False):
        if not str(section_ref).strip():
            continue

        lens = grp["_len"].values
        total_len = float(lens.sum())
        if total_len <= 0:
            total_len = len(grp) * 10.0
        w = lens / total_len

        scores = grp["_score"].values
        priority_score       = float(np.dot(scores, w))
        worst_interval_score = float(scores.max())

        structural_pct = float(np.dot(grp["_structural"].values, w)) * 100
        localised_pct  = float(np.dot(grp["_localised"].values,  w)) * 100
        dressing_pct   = float(np.dot(grp["_dressing"].values,   w)) * 100
        micro_pct      = float(np.dot(grp["_micro"].values,      w)) * 100
        edge_pct       = float(np.dot(grp["_edge"].values,       w)) * 100
        alligator_pct  = float(np.dot(grp["_alligator"].values,  w)) * 100

        # Primary/secondary defects from section-level weighted-avg contributions
        contribs = {}
        for key, col in defect_avgs.items():
            v = float(np.dot(pd.to_numeric(grp[col], errors="coerce").fillna(0).values, w))
            contribs[key] = v * weights.get(key, 0)
        ranked = sorted(contribs.items(), key=lambda x: x[1], reverse=True)
        pri_defect  = ranked[0][0] if ranked else None
        pri_contr   = ranked[0][1] if ranked else None
        sec_defect  = ranked[1][0] if len(ranked) > 1 else None
        sec_contr   = ranked[1][1] if len(ranked) > 1 else None

        def wavg(col):
            if not col or col not in grp.columns:
                return None
            vals = pd.to_numeric(grp[col], errors="coerce")
            if vals.isna().all():
                return None
            return float(np.dot(vals.fillna(0).values, w))

        def wclass(col, ascending=False):
            if not col or col not in grp.columns:
                return None
            vals = grp[col].dropna()
            if vals.empty:
                return None
            v = vals.max() if ascending else vals.min()
            return str(v) if v is not None else None

        rag = _assign_rag(priority_score)
        treatment = _assign_treatment(
            structural_pct / 100, alligator_pct / 100,
            localised_pct / 100, dressing_pct / 100,
            micro_pct / 100, edge_pct / 100,
        )

        sections.append({
            "section_ref": str(section_ref),
            "road_name":   grp[road_col].iloc[0] if road_col else None,
            "net_reference": grp[netref_col].iloc[0] if netref_col else None,
            "urban_rural": grp[urbrur_col].iloc[0] if urbrur_col else None,
            "road_class":  grp[road_class_col].iloc[0] if road_class_col else None,
            "length_m": total_len,
            "road_surface_condition":       wavg(rsc_col),
            "road_surface_condition_class": wclass(rsc_class_col),
            "asphalt_condition":            wavg(asphalt_col),
            "asphalt_condition_class":      wclass(asphalt_class_col),
            "pas2161_category":             wclass(pas_col, ascending=True),
            "priority_score":      round(priority_score, 4),
            "worst_interval_score":round(worst_interval_score, 4),
            "rag_band":  rag,
            "treatment": treatment,
            "primary_defect":              pri_defect,
            "primary_defect_contribution": round(pri_contr, 4) if pri_contr else None,
            "secondary_defect":              sec_defect,
            "secondary_defect_contribution": round(sec_contr, 4) if sec_contr else None,
            "structural_pct": round(structural_pct, 2),
            "localised_pct":  round(localised_pct, 2),
            "dressing_pct":   round(dressing_pct, 2),
            "micro_pct":      round(micro_pct, 2),
            "alligator_pct":  round(alligator_pct, 2),
            "edge_pct":       round(edge_pct, 2),
            **calculate_qc((float(row['_len']), row) for row in grp.to_dict('records')),
        })

    return sections, raw_intervals


def _dedup_by_latest_pass(df: pd.DataFrame, network_key: str) -> tuple[pd.DataFrame, int]:
    """Keep only the most recent (Time UTC) row per (section, from_m, to_m) key.

    Mirrors priority_dst.html step 1: when a section-interval was surveyed on multiple passes,
    keep the latest one so repeat surveys don't double-count. Rows without Time UTC fall back
    to keeping the last one seen. Returns (deduped_df, dup_groups_resolved).
    """
    cfg = NETWORK_CONFIGS.get(network_key, NETWORK_CONFIGS["stroud"])
    cols = df.columns.tolist()
    section_col = _find_col(cols, cfg["section_keys"])
    if not section_col and network_key == "wscc":
        section_col = _find_col(cols, ["WSCCNET"])
    from_col = _find_col(cols, ["Chainage Start", "ChaStart", "From", "FROM", "StartCH", "STARTM", "Start", "from_m"])
    to_col   = _find_col(cols, ["Chainage End", "ChaEnd", "To", "TO", "EndCH", "ENDM", "End", "to_m"])
    time_col = _find_col(cols, ["Time UTC", "Time (UTC)", "TIME_UTC", "Date Time", "DateTime", "Timestamp"])
    if not (section_col and from_col and to_col):
        return df, 0

    df = df.copy()
    df["__key"] = (
        df[section_col].astype(str)
        + "|" + df[from_col].astype(str)
        + "|" + df[to_col].astype(str)
    )
    group_sizes = df.groupby("__key").size()
    dup_groups = int((group_sizes > 1).sum())
    if dup_groups == 0:
        return df.drop(columns=["__key"]), 0

    if time_col:
        parsed_time = pd.to_datetime(df[time_col], errors="coerce")
        df["__time"] = parsed_time
        df = df.sort_values("__time", na_position="first")
    idx_last = df.groupby("__key", sort=False).tail(1).index
    df = df.loc[idx_last].drop(columns=[c for c in ("__key", "__time") if c in df.columns])
    return df, dup_groups


import re as _re
_LINK_COL_PATTERN = _re.compile(r"link|url|hyperlink|video", _re.IGNORECASE)
_EXTRA_PASSTHROUGH_KEYS = [
    "Coverage (total)", "Coverage (valid)", "Total coverage", "Valid coverage", "Filter",
    "Time UTC", "Time (UTC)", "TIME_UTC", "Date Time", "DateTime", "Timestamp",
    "Latitude", "Longitude", "Lat", "Long", "Lon", "LAT", "LON", "LONG",
    "Map Link", "Map link", "Google Street View", "Video Link", "Video URL",
]
_EXTRAS_COL = "__extras_json"


def _recover_hyperlinks_in_df(file_bytes: bytes, df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Scan XLSX for link-shaped columns, rewrite df cells with recovered URLs.

    Recovery order per cell: cell.hyperlink.target → =HYPERLINK() formula → plain http string.
    Returns (df_updated, flattened_warnings, link_col_names).
    """
    try:
        from openpyxl import load_workbook
    except Exception:
        return df, [], []
    try:
        wb = load_workbook(io.BytesIO(file_bytes), read_only=False, data_only=True)
    except Exception:
        return df, [], []

    sheet_name = "Sheet1" if "Sheet1" in wb.sheetnames else wb.sheetnames[0]
    ws = wb[sheet_name]
    header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if not header_row:
        return df, [], []
    headers = [str(h).strip() if h is not None else "" for h in header_row]
    link_cols = [(idx, h) for idx, h in enumerate(headers) if h and _LINK_COL_PATTERN.search(h)]
    if not link_cols:
        return df, [], []

    flattened: list[str] = []
    recovered: dict[str, list[Optional[str]]] = {}

    for col_idx, col_name in link_cols:
        column_letter = ws.cell(row=1, column=col_idx + 1).column_letter
        col_values: list[Optional[str]] = []
        recovered_any = False
        saw_zero = False
        for cell in ws[column_letter][1:]:
            url = None
            if cell.hyperlink and cell.hyperlink.target:
                url = cell.hyperlink.target
            elif isinstance(cell.value, str):
                v = cell.value.strip()
                if v.lower().startswith("http"):
                    url = v
                elif v.upper().startswith("=HYPERLINK("):
                    m = _re.search(r'HYPERLINK\(\s*"([^"]+)"', v, _re.IGNORECASE)
                    if m:
                        url = m.group(1)
            if url:
                recovered_any = True
            elif cell.value == 0 or cell.value == "0":
                saw_zero = True
            col_values.append(url)
        if recovered_any:
            recovered[col_name] = col_values
        elif saw_zero:
            flattened.append(col_name)

    if recovered:
        df = df.copy()
        for col_name, values in recovered.items():
            if col_name in df.columns:
                trimmed = values[:len(df)] + [None] * max(0, len(df) - len(values))
                df[col_name] = trimmed

    return df, flattened, [h for _, h in link_cols]


def _attach_extras_json_column(df: pd.DataFrame, link_col_names: list[str]) -> pd.DataFrame:
    """Serialise per-row extras (link columns + known passthrough columns) as JSON string column."""
    lower = {c.lower(): c for c in df.columns}
    extras_cols: list[str] = [c for c in link_col_names if c in df.columns]
    extras_cols += [c for c in df.columns if c not in extras_cols and any(
        alias in _re.sub(r'[^a-z0-9]', '', c.lower())
        for alias in ('coveragetotal', 'coveragevalid', 'totalcoverage', 'validcoverage')
    )]
    for k in _EXTRA_PASSTHROUGH_KEYS:
        actual = lower.get(k.lower())
        if actual and actual not in extras_cols:
            extras_cols.append(actual)
    if not extras_cols:
        df = df.copy()
        df[_EXTRAS_COL] = ""
        return df

    import json as _json
    import math as _math
    arrs = {c: df[c].tolist() for c in extras_cols}
    out: list[str] = []
    for i in range(len(df)):
        d: dict = {}
        for c in extras_cols:
            v = arrs[c][i]
            if v is None:
                continue
            if isinstance(v, float) and _math.isnan(v):
                continue
            if not isinstance(v, (str, int, float, bool)):
                v = str(v)
            d[c] = v
        out.append(_json.dumps(d, ensure_ascii=False) if d else "")
    df = df.copy()
    df[_EXTRAS_COL] = out
    return df


def _parse_info_sheet(file_bytes: bytes) -> dict:
    """Extract Info-sheet metadata from a Vaisala RoadAI XLSX. Empty dict if none / not xlsx."""
    try:
        from openpyxl import load_workbook
    except Exception:
        return {}
    try:
        wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception:
        return {}
    if "Info" not in wb.sheetnames:
        return {}
    info_ws = wb["Info"]
    lines: list[str] = []
    for row in info_ws.iter_rows(values_only=True):
        first = row[0] if row else None
        if first is not None:
            lines.append(str(first))
    text = "\n".join(lines)
    import re
    def _match(pattern):
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else None
    return {
        "district": _match(r"DISTRICT:\s*\n\s*-\s*([^\n]+)")
                  or _match(r"Client:\s*([^\n]+)"),
        "road_class": _match(r"ROADCLASS:\s*\n\s*-\s*'?([^'\n]+)'?"),
        "from_date": _match(r"From date:\s*([^\s(]+)"),
        "to_date":   _match(r"To date:\s*([^\s(]+)"),
        "multiple_drives": _match(r"Multiple drives:\s*'?([^'\n]+)'?"),
        "interval_length": _match(r"Segment interval length:\s*(\d+)"),
    }


def parse_raw_xlsx(
    file_bytes: bytes,
    network_key: str,
    weights: Optional[dict] = None,
    dedup_strategy: str = "latest",
) -> dict:
    weights = weights or RAG_VALIDATED_WEIGHTS
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), header=0, engine="calamine")
    except Exception:
        df = pd.read_excel(io.BytesIO(file_bytes), header=0)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")
    df, flattened_link_warnings, link_col_names = _recover_hyperlinks_in_df(file_bytes, df)
    df = _attach_extras_json_column(df, link_col_names)
    dup_groups = 0
    if dedup_strategy == "latest":
        df, dup_groups = _dedup_by_latest_pass(df, network_key)
    row_count = len(df)
    sections, intervals = _aggregate_intervals(df, network_key, weights)
    drift = detect_weight_drift(weights)
    info_meta = _parse_info_sheet(file_bytes)
    return {
        "row_count": row_count,
        "sections": sections,
        "intervals": intervals,
        "drift": drift,
        "dup_groups": dup_groups,
        "info_meta": info_meta,
        "flattened_link_warnings": flattened_link_warnings,
    }


def parse_raw_csv(
    file_bytes: bytes,
    network_key: str,
    weights: Optional[dict] = None,
    dedup_strategy: str = "latest",
) -> dict:
    weights = weights or RAG_VALIDATED_WEIGHTS
    df = pd.read_csv(io.BytesIO(file_bytes))
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")
    # CSV never carries live hyperlinks; still build extras_json for passthrough columns
    df = _attach_extras_json_column(df, [])
    dup_groups = 0
    if dedup_strategy == "latest":
        df, dup_groups = _dedup_by_latest_pass(df, network_key)
    row_count = len(df)
    sections, intervals = _aggregate_intervals(df, network_key, weights)
    drift = detect_weight_drift(weights)
    return {
        "row_count": row_count,
        "sections": sections,
        "intervals": intervals,
        "drift": drift,
        "dup_groups": dup_groups,
        "info_meta": {},
        "flattened_link_warnings": [],
    }


def parse_shp_export(file_bytes: bytes) -> dict:
    """Parse a SHP export produced by priority_dst.html (pre-scored sections)."""
    import zipfile, tempfile, os

    with tempfile.TemporaryDirectory() as tmpdir:
        # Expect a zip containing .shp/.dbf/.shx
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            zf.extractall(tmpdir)
        shp_files = [f for f in os.listdir(tmpdir) if f.endswith(".shp")]
        if not shp_files:
            raise ValueError("No .shp file found in zip")
        gdf = gpd.read_file(os.path.join(tmpdir, shp_files[0]))

    sections = []
    for _, row in gdf.iterrows():
        section = {}
        for shp_field, db_field in SHP_FIELD_MAP.items():
            val = row.get(shp_field)
            section[db_field] = _safe(val)
        sections.append(section)

    return {"row_count": len(sections), "sections": sections, "intervals": [], "drift": [], "dup_groups": 0, "info_meta": {}}
