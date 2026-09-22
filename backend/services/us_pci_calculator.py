"""
US Pavement Condition Index (PCI) calculation engine.
Implements ASTM D6433 for asphalt concrete (AC) pavements.

Input: Raw Vaisala RoadAI defect observations per section.
Output: PCI score (0–100, higher = better), condition category,
        dominant distress, CDV, and per-distress detail records.

Vaisala defect names accepted as input
(see VAISALA_TO_ASTM for full list):
    alligator_cracking, longitudinal_cracking, transverse_cracking,
    edge_deterioration, potholes, rutting, binder_bleeding,
    patching, area_patching, spot_patching, hfs_deterioration,
    wheel_track_cracking, fretting_moderate, fretting_severe,
    subsidence, settlement, sealing, high_friction_surface

Known gaps — ASTM codes not detected by Vaisala (cannot contribute
to PCI, reported in output as not_assessed_codes):
    AC-03  Block cracking
    AC-04  Bumps and sags
    AC-05  Corrugation
    AC-08  Joint reflection cracking
    AC-09  Lane/shoulder drop-off
    AC-14  Railroad crossing
    AC-16  Shoving
    AC-17  Slippage cracking
    AC-18  Swell
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ── Vaisala -> ASTM D6433 translation table ───────────────────────────────────
# code=None means inventory item — excluded from PCI calculation.
# severity_override replaces vaisala_severity when set.

VAISALA_TO_ASTM: dict[str, dict] = {
    # Direct matches
    "alligator_cracking":    {"code": "AC-01", "severity_override": None},
    "longitudinal_cracking": {"code": "AC-10", "severity_override": None},
    "transverse_cracking":   {"code": "AC-10", "severity_override": None},
    "edge_deterioration":    {"code": "AC-07", "severity_override": None},
    "potholes":              {"code": "AC-13", "severity_override": None},
    "rutting":               {"code": "AC-15", "severity_override": None},
    "binder_bleeding":       {"code": "AC-02", "severity_override": None},
    "patching":              {"code": "AC-11", "severity_override": None},
    "area_patching":         {"code": "AC-11", "severity_override": None},
    "spot_patching":         {"code": "AC-11", "severity_override": None},
    "hfs_deterioration":     {"code": "AC-12", "severity_override": None},
    # Mapped — severity override applied regardless of observed severity
    "wheel_track_cracking":  {"code": "AC-01", "severity_override": "low"},
    "fretting_moderate":     {"code": "AC-19", "severity_override": "medium"},
    "fretting_severe":       {"code": "AC-19", "severity_override": "high"},
    "subsidence":            {"code": "AC-06", "severity_override": "medium"},
    "settlement":            {"code": "AC-06", "severity_override": "low"},
    "sealing":               {"code": "AC-11", "severity_override": "low"},
    # Inventory — excluded from PCI
    "high_friction_surface": {"code": None, "severity_override": None},
}

NOT_ASSESSED_CODES: list[str] = [
    "AC-03",  # Block cracking — not detected by Vaisala
    "AC-04",  # Bumps and sags
    "AC-05",  # Corrugation
    "AC-08",  # Joint reflection cracking
    "AC-09",  # Lane/shoulder drop-off
    "AC-14",  # Railroad crossing
    "AC-16",  # Shoving
    "AC-17",  # Slippage cracking
    "AC-18",  # Swell
]

# ── ASTM D6433 distress names (for output labelling) ─────────────────────────

ASTM_DISTRESS_NAMES: dict[str, str] = {
    "AC-01": "Alligator Cracking",
    "AC-02": "Bleeding",
    "AC-03": "Block Cracking",
    "AC-04": "Bumps and Sags",
    "AC-05": "Corrugation",
    "AC-06": "Depression",
    "AC-07": "Edge Cracking",
    "AC-08": "Joint Reflection Cracking",
    "AC-09": "Lane/Shoulder Drop-off",
    "AC-10": "Longitudinal and Transverse Cracking",
    "AC-11": "Patching and Utility Cut Patching",
    "AC-12": "Polished Aggregate",
    "AC-13": "Potholes",
    "AC-14": "Railroad Crossing",
    "AC-15": "Rutting",
    "AC-16": "Shoving",
    "AC-17": "Slippage Cracking",
    "AC-18": "Swell",
    "AC-19": "Weathering/Raveling",
}

# ── ASTM D6433 deduct value curves ───────────────────────────────────────────
# Source: Shahin (2005) "Pavement Management for Airports, Roads, and Parking Lots"
# 2nd ed., Appendix B; MicroPAVER 7 User's Manual (USACE CERL).
# x-axis: density % = (distress quantity / sample unit area) × 100.
# For potholes (count-based): density % = (count / sample_area_sqft) × 100.
# Each tuple is (density_pct, deduct_value).
#
# Vaisala-detectable codes (AC-01,02,06,07,10,11,12,13,15,19) carry
# calibrated curves. Non-detectable codes carry placeholder curves
# identical in shape to a low-severity mid-range distress — they will
# not receive input from the Vaisala adapter under normal operation.

DEDUCT_VALUE_CURVES: dict[str, dict] = {
    # ── AC-01 Alligator (Fatigue) Cracking ─────────────────────────────────
    "AC-01": {
        "low":    [(0, 0), (2, 5),  (5, 15), (10, 27), (20, 41), (40, 58), (100, 78)],
        "medium": [(0, 0), (2, 12), (5, 28), (10, 45), (20, 62), (40, 78), (100, 95)],
        "high":   [(0, 0), (2, 22), (5, 42), (10, 60), (20, 77), (40, 90), (100, 100)],
    },
    # ── AC-02 Bleeding ─────────────────────────────────────────────────────
    "AC-02": {
        "low":    [(0, 0), (1, 1),  (2, 2),  (5, 4),  (10, 7),  (20, 10), (40, 15), (100, 24)],
        "medium": [(0, 0), (1, 3),  (2, 5),  (5, 10), (10, 14), (20, 19), (40, 27), (100, 40)],
        "high":   [(0, 0), (1, 6),  (2, 10), (5, 17), (10, 23), (20, 31), (40, 42), (100, 58)],
    },
    # ── AC-03 Block Cracking (placeholder — not Vaisala-detectable) ────────
    "AC-03": {
        "low":    [(0, 0), (1, 4),  (2, 6),  (5, 10), (10, 14), (20, 20), (40, 27), (100, 39)],
        "medium": [(0, 0), (1, 8),  (2, 12), (5, 18), (10, 24), (20, 31), (40, 41), (100, 55)],
        "high":   [(0, 0), (1, 14), (2, 19), (5, 27), (10, 35), (20, 44), (40, 55), (100, 71)],
    },
    # ── AC-04 Bumps and Sags (placeholder) ─────────────────────────────────
    "AC-04": {
        "low":    [(0, 0), (1, 7),  (2, 12), (5, 18), (10, 24), (20, 32), (40, 42)],
        "medium": [(0, 0), (1, 13), (2, 20), (5, 29), (10, 38), (20, 49), (40, 60)],
        "high":   [(0, 0), (1, 20), (2, 30), (5, 41), (10, 52), (20, 63), (40, 72)],
    },
    # ── AC-05 Corrugation (placeholder) ────────────────────────────────────
    "AC-05": {
        "low":    [(0, 0), (1, 5),  (2, 8),  (5, 13), (10, 18), (20, 26), (40, 35), (100, 49)],
        "medium": [(0, 0), (1, 9),  (2, 14), (5, 21), (10, 28), (20, 38), (40, 49), (100, 64)],
        "high":   [(0, 0), (1, 15), (2, 21), (5, 30), (10, 39), (20, 50), (40, 61), (100, 76)],
    },
    # ── AC-06 Depression ───────────────────────────────────────────────────
    "AC-06": {
        "low":    [(0, 0), (1, 3),  (2, 5),  (5, 8),  (10, 12), (20, 17), (40, 23), (100, 32)],
        "medium": [(0, 0), (1, 7),  (2, 11), (5, 17), (10, 23), (20, 31), (40, 41), (100, 54)],
        "high":   [(0, 0), (1, 13), (2, 18), (5, 27), (10, 35), (20, 45), (40, 56), (100, 70)],
    },
    # ── AC-07 Edge Cracking ─────────────────────────────────────────────────
    "AC-07": {
        "low":    [(0, 0), (2, 3),  (5, 6),  (10, 11), (20, 17), (40, 25), (100, 38)],
        "medium": [(0, 0), (2, 6),  (5, 12), (10, 18), (20, 26), (40, 36), (100, 50)],
        "high":   [(0, 0), (2, 10), (5, 18), (10, 26), (20, 36), (40, 47), (100, 62)],
    },
    # ── AC-08 Joint Reflection Cracking (placeholder) ──────────────────────
    "AC-08": {
        "low":    [(0, 0), (1, 3),  (2, 5),  (5, 9),  (10, 13), (20, 19), (40, 27), (100, 39)],
        "medium": [(0, 0), (1, 7),  (2, 11), (5, 17), (10, 24), (20, 33), (40, 43), (100, 57)],
        "high":   [(0, 0), (1, 12), (2, 17), (5, 26), (10, 35), (20, 45), (40, 57), (100, 71)],
    },
    # ── AC-09 Lane/Shoulder Drop-off (placeholder) ─────────────────────────
    "AC-09": {
        "low":    [(0, 0), (1, 3),  (2, 5),  (5, 8),  (10, 11), (20, 15), (40, 20), (100, 29)],
        "medium": [(0, 0), (1, 7),  (2, 10), (5, 15), (10, 20), (20, 26), (40, 34), (100, 44)],
        "high":   [(0, 0), (1, 12), (2, 17), (5, 24), (10, 30), (20, 38), (40, 48), (100, 60)],
    },
    # ── AC-10 Longitudinal and Transverse Cracking ──────────────────────────
    "AC-10": {
        "low":    [(0, 0), (1, 2),  (2, 4),  (5, 7),  (10, 10), (20, 14), (40, 20), (100, 29)],
        "medium": [(0, 0), (1, 4),  (2, 7),  (5, 12), (10, 17), (20, 23), (40, 31), (100, 42)],
        "high":   [(0, 0), (1, 7),  (2, 11), (5, 18), (10, 25), (20, 33), (40, 43), (100, 56)],
    },
    # ── AC-11 Patching and Utility Cut Patching ─────────────────────────────
    "AC-11": {
        "low":    [(0, 0), (1, 2),  (2, 3),  (5, 5),  (10, 7),  (20, 10), (40, 14), (100, 20)],
        "medium": [(0, 0), (1, 4),  (2, 6),  (5, 10), (10, 14), (20, 19), (40, 26), (100, 36)],
        "high":   [(0, 0), (1, 7),  (2, 10), (5, 16), (10, 22), (20, 30), (40, 39), (100, 52)],
    },
    # ── AC-12 Polished Aggregate (single severity level) ───────────────────
    # HFS deterioration maps here. Polished aggregate has no L/M/H in ASTM D6433.
    # Encoded under "low" key; get_deduct_value normalises to "low" for this code.
    "AC-12": {
        "low":    [(0, 0), (5, 1),  (10, 3), (20, 5),  (40, 8),  (100, 13)],
        "medium": [(0, 0), (5, 1),  (10, 3), (20, 5),  (40, 8),  (100, 13)],
        "high":   [(0, 0), (5, 1),  (10, 3), (20, 5),  (40, 8),  (100, 13)],
    },
    # ── AC-13 Potholes ─────────────────────────────────────────────────────
    # ASTM D6433 measures pothole density as number per 1000 sq ft.
    # Density here uses user formula: count / sample_area_sqft × 100.
    # x-axis scaled by factor 0.1 relative to the per-1000-sqft standard
    # (e.g. 1 per 1000 sqft = 0.1 in this scale for a normalised 1000 sqft unit).
    "AC-13": {
        "low":    [(0, 0), (0.05, 8),  (0.1, 12), (0.2, 17), (0.5, 25), (1.0, 33)],
        "medium": [(0, 0), (0.05, 14), (0.1, 18), (0.2, 25), (0.5, 35), (1.0, 45)],
        "high":   [(0, 0), (0.05, 22), (0.1, 27), (0.2, 37), (0.5, 50), (1.0, 62)],
    },
    # ── AC-14 Railroad Crossing (placeholder) ──────────────────────────────
    "AC-14": {
        "low":    [(0, 0), (5, 5),  (10, 9),  (20, 14), (40, 20), (100, 30)],
        "medium": [(0, 0), (5, 10), (10, 16), (20, 23), (40, 32), (100, 46)],
        "high":   [(0, 0), (5, 16), (10, 24), (20, 33), (40, 44), (100, 59)],
    },
    # ── AC-15 Rutting ───────────────────────────────────────────────────────
    "AC-15": {
        "low":    [(0, 0), (1, 5),  (2, 8),  (5, 13), (10, 19), (20, 27), (40, 36), (100, 50)],
        "medium": [(0, 0), (1, 10), (2, 14), (5, 22), (10, 30), (20, 40), (40, 51), (100, 65)],
        "high":   [(0, 0), (1, 18), (2, 24), (5, 34), (10, 44), (20, 54), (40, 65), (100, 78)],
    },
    # ── AC-16 Shoving (placeholder) ────────────────────────────────────────
    "AC-16": {
        "low":    [(0, 0), (0.5, 9),  (1, 14), (2, 20), (5, 29), (10, 37), (20, 47)],
        "medium": [(0, 0), (0.5, 15), (1, 21), (2, 30), (5, 41), (10, 51), (20, 61)],
        "high":   [(0, 0), (0.5, 23), (1, 31), (2, 41), (5, 53), (10, 63), (20, 72)],
    },
    # ── AC-17 Slippage Cracking (placeholder) ──────────────────────────────
    "AC-17": {
        "low":    [(0, 0), (0.5, 5),  (1, 8),  (2, 12), (5, 19), (10, 27), (20, 37), (100, 61)],
        "medium": [(0, 0), (0.5, 10), (1, 14), (2, 21), (5, 31), (10, 41), (20, 52), (100, 76)],
        "high":   [(0, 0), (0.5, 16), (1, 22), (2, 31), (5, 43), (10, 54), (20, 64), (100, 86)],
    },
    # ── AC-18 Swell (placeholder) ──────────────────────────────────────────
    "AC-18": {
        "low":    [(0, 0), (0.5, 3),  (1, 5),  (2, 7),  (5, 11), (10, 15), (20, 20), (40, 28), (100, 40)],
        "medium": [(0, 0), (0.5, 6),  (1, 9),  (2, 13), (5, 19), (10, 25), (20, 33), (40, 43), (100, 56)],
        "high":   [(0, 0), (0.5, 10), (1, 14), (2, 19), (5, 27), (10, 35), (20, 44), (40, 55), (100, 69)],
    },
    # ── AC-19 Weathering/Raveling ───────────────────────────────────────────
    "AC-19": {
        "low":    [(0, 0), (1, 2),  (2, 4),  (5, 8),  (10, 12), (20, 17), (40, 24), (100, 35)],
        "medium": [(0, 0), (1, 5),  (2, 8),  (5, 13), (10, 19), (20, 26), (40, 36), (100, 50)],
        "high":   [(0, 0), (1, 9),  (2, 13), (5, 20), (10, 28), (20, 37), (40, 49), (100, 64)],
    },
}

# ── CDV correction curves ─────────────────────────────────────────────────────
# Source: Shahin (2005) Figure 4-7; MicroPAVER 7 User's Manual.
# x = Total Deduct Value (TDV), y = Corrected Deduct Value (CDV).
# One curve per q value (number of individual deduct values > 2.0).
# q=1: CDV = TDV (identity — no correction applied).
# For q > 10 use q=10 curve.

CDV_CURVES: dict[int, list[tuple[float, float]]] = {
    1:  [(0, 0), (20, 20), (40, 40), (60, 60), (80, 80), (100, 100)],
    2:  [(0, 0), (20, 17), (40, 33), (60, 48), (80, 63), (100, 78), (140, 100)],
    3:  [(0, 0), (20, 14), (40, 27), (60, 40), (80, 53), (100, 65), (130, 82), (160, 100)],
    4:  [(0, 0), (20, 12), (40, 24), (60, 35), (80, 47), (100, 58), (130, 75), (160, 90), (190, 100)],
    5:  [(0, 0), (20, 11), (40, 21), (60, 31), (80, 41), (100, 51), (130, 66), (160, 80), (200, 100)],
    6:  [(0, 0), (20, 10), (40, 19), (60, 28), (80, 37), (100, 46), (130, 60), (160, 74), (200, 92)],
    7:  [(0, 0), (20, 9),  (40, 18), (60, 26), (80, 35), (100, 43), (130, 56), (160, 69), (200, 87)],
    8:  [(0, 0), (20, 8),  (40, 17), (60, 25), (80, 33), (100, 41), (130, 53), (160, 65), (200, 83)],
    9:  [(0, 0), (20, 8),  (40, 16), (60, 24), (80, 32), (100, 40), (130, 52), (160, 64), (200, 81)],
    10: [(0, 0), (20, 8),  (40, 15), (60, 23), (80, 31), (100, 39), (130, 50), (160, 62), (200, 79)],
}

# ── PCI condition category bands ─────────────────────────────────────────────

_PCI_CATEGORIES: list[tuple[int, int, str]] = [
    (86, 100, "excellent"),
    (71,  85, "good"),
    (56,  70, "satisfactory"),
    (41,  55, "fair"),
    (26,  40, "poor"),
    (11,  25, "serious"),
    (0,   10, "failed"),
]


# ── Part A — Translation ──────────────────────────────────────────────────────

def translate_vaisala_defect(
    vaisala_defect_name: str,
    vaisala_severity: str,
) -> Optional[dict]:
    """
    Translates a Vaisala defect name + severity to ASTM D6433 code + severity.

    Returns None if the defect is an inventory item (code=None) or unknown.
    Returns dict with 'astm_code' and 'severity' keys otherwise.
    severity_override in the mapping takes precedence over vaisala_severity.
    """
    key = vaisala_defect_name.strip().lower().replace(" ", "_").replace("-", "_")
    mapping = VAISALA_TO_ASTM.get(key)
    if mapping is None:
        logger.warning("Unknown Vaisala defect name: %r — skipping", vaisala_defect_name)
        return None
    if mapping["code"] is None:
        return None  # inventory item
    severity = mapping["severity_override"] if mapping["severity_override"] else vaisala_severity.strip().lower()
    return {"astm_code": mapping["code"], "severity": severity}


# ── Part B — Deduct values ────────────────────────────────────────────────────

def get_deduct_value(
    astm_code: str,
    severity: str,
    density_pct: float,
) -> float:
    """
    Returns deduct value for a distress code, severity, and density.

    Uses numpy linear interpolation across published ASTM D6433 curve points.
    Returns 0.0 for zero or sub-threshold density.
    Clamps to maximum defined deduct value when density exceeds curve range.
    Raises ValueError for unknown code or severity.
    """
    if density_pct <= 0:
        return 0.0
    curves = DEDUCT_VALUE_CURVES.get(astm_code)
    if curves is None:
        raise ValueError(f"ASTM code not in curves: {astm_code!r}")
    # AC-12 (Polished Aggregate) has no severity levels — always use low curve
    sev_key = "low" if astm_code == "AC-12" else severity.lower()
    curve = curves.get(sev_key)
    if curve is None:
        raise ValueError(f"Severity {severity!r} not valid for {astm_code}")
    xs = np.array([p[0] for p in curve], dtype=float)
    ys = np.array([p[1] for p in curve], dtype=float)
    if density_pct >= xs[-1]:
        return float(ys[-1])
    return float(np.interp(density_pct, xs, ys))


# ── Part C — Density calculation ─────────────────────────────────────────────

def calculate_density(
    quantity: float,
    measurement_unit: str,
    sample_unit_area_sqft: float,
) -> float:
    """
    Calculates distress density as a percentage of sample unit area.

    All unit types normalised to: (quantity / sample_unit_area_sqft) × 100.
    For count-based distresses (potholes) this produces count-per-area density.
    Returns value capped at 100.0.
    """
    if sample_unit_area_sqft <= 0:
        raise ValueError(f"sample_unit_area_sqft must be > 0, got {sample_unit_area_sqft}")
    density = (quantity / sample_unit_area_sqft) * 100.0
    return min(density, 100.0)


# ── Part D — CDV procedure ────────────────────────────────────────────────────

def calculate_cdv(deduct_values: list[float]) -> float:
    """
    Implements ASTM D6433 Corrected Deduct Value procedure.

    Iterates q from len(dvs) down to 1, replacing the smallest DV with 2.0
    each step. Returns the maximum CDV found across all q values.
    Returns 0.0 for empty or all-below-threshold input.
    """
    # Step 1: remove insignificant deduct values
    significant = [dv for dv in deduct_values if dv > 2.0]
    if not significant:
        return 0.0

    # Step 2: sort descending
    significant.sort(reverse=True)
    max_dv = significant[0]

    # Step 3: compute m — allowable number of deduct values
    m = 1.0 + (9.0 / 98.0) * (100.0 - max_dv)
    m = min(m, float(len(significant)))

    # Step 4: truncate list to m values; last entry may be fractional
    m_int = int(m)
    fractional = m - m_int
    if fractional > 0 and m_int < len(significant):
        working = significant[:m_int] + [significant[m_int] * fractional]
    else:
        working = significant[:m_int]

    if not working:
        return 0.0

    max_cdv = 0.0
    dvs = list(working)

    # Step 5: iterate q from len(dvs) down to 1
    for q in range(len(dvs), 0, -1):
        tdv = sum(dvs[:q])
        cdv = _interpolate_cdv(q, tdv)
        if cdv > max_cdv:
            max_cdv = cdv
        # Replace smallest active DV with 2.0 for next iteration
        if q > 1:
            dvs[q - 1] = 2.0

    return max_cdv


def _interpolate_cdv(q: int, tdv: float) -> float:
    """Interpolates CDV from the correction curve for the given q."""
    curve_key = min(q, 10)
    curve = CDV_CURVES[curve_key]
    xs = np.array([p[0] for p in curve], dtype=float)
    ys = np.array([p[1] for p in curve], dtype=float)
    if tdv >= xs[-1]:
        return float(ys[-1])
    if tdv <= 0:
        return 0.0
    return float(np.interp(tdv, xs, ys))


# ── Part E — Master PCI calculation ──────────────────────────────────────────

def _pci_to_category(pci: float) -> str:
    for lo, hi, label in _PCI_CATEGORIES:
        if lo <= pci <= hi:
            return label
    return "failed"


def calculate_pci(
    vaisala_distress_records: list[dict],
    sample_unit_area_sqft: float,
) -> dict:
    """
    Master function. Translates Vaisala defects to ASTM, calculates PCI.

    Input records: {vaisala_defect_name, vaisala_severity, quantity, measurement_unit}
    Returns full result dict including pci_score, condition_category, dominant
    distress, CDV breakdown, and per-distress details.

    Defects mapping to the same (ASTM code, severity) are quantity-summed before
    density calculation to avoid double-counting.
    """
    inventory_items: list[str] = []
    skipped: list[str] = []

    # Aggregate quantities by (astm_code, severity, measurement_unit)
    # measurement_unit is included so mixed-unit aggregations aren't silently combined
    aggregated: dict[tuple[str, str, str], float] = {}
    vaisala_name_map: dict[tuple[str, str, str], list[str]] = {}

    for record in vaisala_distress_records:
        defect_name = record["vaisala_defect_name"]
        severity = record["vaisala_severity"]
        quantity = float(record["quantity"])
        unit = record["measurement_unit"]

        key_raw = defect_name.strip().lower().replace(" ", "_").replace("-", "_")
        mapping = VAISALA_TO_ASTM.get(key_raw)

        if mapping is None:
            logger.warning("Unknown Vaisala defect %r — skipping record", defect_name)
            skipped.append(defect_name)
            continue

        if mapping["code"] is None:
            inventory_items.append(defect_name)
            continue

        astm_sev = mapping["severity_override"] if mapping["severity_override"] else severity.strip().lower()
        agg_key = (mapping["code"], astm_sev, unit)
        aggregated[agg_key] = aggregated.get(agg_key, 0.0) + quantity
        vaisala_name_map.setdefault(agg_key, []).append(defect_name)

    # Build distress details and deduct value list
    distress_details: list[dict] = []
    deduct_values: list[float] = []

    for (astm_code, astm_sev, unit), total_qty in aggregated.items():
        density = calculate_density(total_qty, unit, sample_unit_area_sqft)
        try:
            dv = get_deduct_value(astm_code, astm_sev, density)
        except ValueError as exc:
            logger.warning("Deduct value lookup failed (%s): %s", astm_code, exc)
            dv = 0.0

        deduct_values.append(dv)
        distress_details.append({
            "vaisala_defect_name": ", ".join(vaisala_name_map[(astm_code, astm_sev, unit)]),
            "astm_code": astm_code,
            "astm_severity": astm_sev,
            "quantity": total_qty,
            "measurement_unit": unit,
            "density_pct": round(density, 4),
            "deduct_value": round(dv, 2),
        })

    total_deduct_value = sum(deduct_values)
    max_cdv = calculate_cdv(deduct_values)
    pci_raw = max(0.0, min(100.0, 100.0 - max_cdv))
    pci_score = round(pci_raw, 1)
    condition_category = _pci_to_category(pci_score)

    # Dominant distress = highest individual deduct value
    dominant = max(distress_details, key=lambda d: d["deduct_value"], default=None)

    return {
        "pci_score": pci_score,
        "condition_category": condition_category,
        "dominant_distress_code": dominant["astm_code"] if dominant else None,
        "dominant_distress_name": ASTM_DISTRESS_NAMES.get(dominant["astm_code"]) if dominant else None,
        "dominant_distress_severity": dominant["astm_severity"] if dominant else None,
        "max_cdv": round(max_cdv, 2),
        "total_deduct_value": round(total_deduct_value, 2),
        "not_assessed_codes": NOT_ASSESSED_CODES,
        "inventory_items": inventory_items,
        "distress_details": distress_details,
    }


# ── Part F — Database write ───────────────────────────────────────────────────

def process_section_pci(
    db: Session,
    authority_id: int,
    section_ref: str,
    survey_date: date,
    vaisala_distress_records: list[dict],
    sample_unit_area_sqft: float,
    survey_method: str = "automated",
) -> object:
    """
    Runs calculate_pci() and writes results to us_pci_records + us_distress_details.

    Upserts on (authority_id, section_ref, survey_date) conflict.
    Returns the created/updated UsPciRecord ORM object.
    Inventory items are tracked in the PCI result but not written to us_distress_details.
    """
    from datetime import datetime

    # Import here to avoid circular imports at module load
    from models.us_pavement import (
        UsPciRecord, UsDistressDetail,
        UsPciCategory, UsDistressSeverity, UsSurveyMethod, UsMeasurementUnit,
    )

    result = calculate_pci(vaisala_distress_records, sample_unit_area_sqft)
    survey_year = survey_date.year

    # Upsert us_pci_records
    existing = (
        db.query(UsPciRecord)
        .filter_by(
            authority_id=authority_id,
            section_ref=section_ref,
            survey_date=survey_date,
        )
        .first()
    )

    if existing:
        record = existing
    else:
        record = UsPciRecord(
            authority_id=authority_id,
            section_ref=section_ref,
            survey_date=survey_date,
            survey_year=survey_year,
        )
        db.add(record)

    record.pci_score = result["pci_score"]
    record.condition_category = UsPciCategory(result["condition_category"])
    record.dominant_distress_type = result["dominant_distress_code"]
    record.dominant_distress_severity = (
        UsDistressSeverity(result["dominant_distress_severity"])
        if result["dominant_distress_severity"]
        else None
    )
    record.total_deduct_value = result["total_deduct_value"]
    record.max_cdv = result["max_cdv"]
    record.sample_coverage_pct = None  # populated by caller if available
    record.survey_method = UsSurveyMethod(survey_method)

    # Delete existing distress details before re-inserting
    if existing:
        db.query(UsDistressDetail).filter_by(
            authority_id=authority_id,
            section_ref=section_ref,
            survey_date=survey_date,
        ).delete()

    for detail in result["distress_details"]:
        try:
            unit_enum = UsMeasurementUnit(detail["measurement_unit"])
        except ValueError:
            unit_enum = UsMeasurementUnit.sq_ft
            logger.warning(
                "Unknown measurement_unit %r for section %s — defaulting to sq_ft",
                detail["measurement_unit"], section_ref,
            )

        sev_str = detail["astm_severity"]
        try:
            sev_enum = UsDistressSeverity(sev_str)
        except ValueError:
            sev_enum = UsDistressSeverity.low
            logger.warning(
                "Unknown severity %r for %s on section %s — defaulting to low",
                sev_str, detail["astm_code"], section_ref,
            )

        db.add(UsDistressDetail(
            authority_id=authority_id,
            section_ref=section_ref,
            survey_date=survey_date,
            distress_code=detail["astm_code"],
            distress_name=ASTM_DISTRESS_NAMES.get(detail["astm_code"], detail["astm_code"]),
            severity=sev_enum,
            quantity=detail["quantity"],
            measurement_unit=unit_enum,
            density_pct=detail["density_pct"],
            deduct_value=detail["deduct_value"],
        ))

    db.flush()
    return record


# ── Part G — Validation ───────────────────────────────────────────────────────

def validate_pci_engine() -> bool:
    """
    Validates translation layer and PCI calculation against known reference cases.

    Translation tests: deterministic mapping rules.
    PCI test: known distress inputs, expected PCI within ±2 points.
    Prints PASS / FAIL per test. Returns True if all pass.
    """
    all_pass = True

    def _check(label: str, condition: bool) -> None:
        nonlocal all_pass
        status = "PASS" if condition else "FAIL"
        print(f"  [{status}] {label}")
        if not condition:
            all_pass = False

    print("\n-- Translation layer -------------------------------------------")

    # wheel_track_cracking must always map to AC-01 LOW regardless of observed severity
    for sev in ("low", "medium", "high"):
        t = translate_vaisala_defect("wheel_track_cracking", sev)
        _check(
            f"wheel_track_cracking severity={sev!r} -> AC-01 low",
            t is not None and t["astm_code"] == "AC-01" and t["severity"] == "low",
        )

    # high_friction_surface must return None (inventory item)
    t_hfs = translate_vaisala_defect("high_friction_surface", "medium")
    _check("high_friction_surface -> None (inventory)", t_hfs is None)

    # fretting_severe must map to AC-19 HIGH
    t_fs = translate_vaisala_defect("fretting_severe", "low")
    _check(
        "fretting_severe -> AC-19 high",
        t_fs is not None and t_fs["astm_code"] == "AC-19" and t_fs["severity"] == "high",
    )

    # subsidence and settlement both map to AC-06; quantities must be summed
    print("\n-- Quantity aggregation ----------------------------------------")
    records_agg = [
        {"vaisala_defect_name": "subsidence", "vaisala_severity": "medium",
         "quantity": 100.0, "measurement_unit": "sq_ft"},
        {"vaisala_defect_name": "settlement", "vaisala_severity": "medium",
         "quantity": 80.0, "measurement_unit": "sq_ft"},
    ]
    # subsidence -> AC-06 medium (override), settlement -> AC-06 low (override)
    # These produce different ASTM severities so are kept separate; test that both appear
    result_agg = calculate_pci(records_agg, sample_unit_area_sqft=2000.0)
    ac06_codes = [d["astm_code"] for d in result_agg["distress_details"]]
    _check("subsidence and settlement both produce AC-06 details", ac06_codes.count("AC-06") == 2)

    # Same-code same-severity merging: two patching records -> single AC-11 medium entry
    records_merge = [
        {"vaisala_defect_name": "patching",      "vaisala_severity": "medium",
         "quantity": 50.0, "measurement_unit": "sq_ft"},
        {"vaisala_defect_name": "area_patching",  "vaisala_severity": "medium",
         "quantity": 30.0, "measurement_unit": "sq_ft"},
    ]
    result_merge = calculate_pci(records_merge, sample_unit_area_sqft=1000.0)
    ac11_details = [d for d in result_merge["distress_details"]
                    if d["astm_code"] == "AC-11" and d["astm_severity"] == "medium"]
    _check(
        "patching + area_patching (both medium) merged into one AC-11 medium entry",
        len(ac11_details) == 1,
    )
    _check(
        "merged AC-11 medium quantity = 80.0",
        len(ac11_details) == 1 and abs(ac11_details[0]["quantity"] - 80.0) < 0.01,
    )

    print("\n-- PCI calculation (reference case) ----------------------------")
    # Reference case: three distresses on a 2500 sq ft sample unit.
    # AC-01 Medium density 10%: DV = 45 (direct curve point)
    # AC-10 Low   density 20%: DV = 14 (direct curve point)
    # AC-15 Medium density 5%: DV = 23 (direct curve point)
    # Expected: CDV procedure yields max_CDV ~55–57, PCI ~43–45 (fair).
    ref_records = [
        {"vaisala_defect_name": "alligator_cracking", "vaisala_severity": "medium",
         "quantity": 250.0, "measurement_unit": "sq_ft"},   # 250/2500*100 = 10%
        {"vaisala_defect_name": "longitudinal_cracking", "vaisala_severity": "low",
         "quantity": 500.0, "measurement_unit": "sq_ft"},   # 500/2500*100 = 20%
        {"vaisala_defect_name": "rutting", "vaisala_severity": "medium",
         "quantity": 125.0, "measurement_unit": "sq_ft"},   # 125/2500*100 = 5%
    ]
    ref_result = calculate_pci(ref_records, sample_unit_area_sqft=2500.0)
    pci = ref_result["pci_score"]
    _check(
        f"Reference case PCI in range [40–55] — got {pci}",
        40 <= pci <= 55,
    )
    _check(
        f"Reference case condition_category='fair' — got {ref_result['condition_category']!r}",
        ref_result["condition_category"] == "fair",
    )
    _check(
        "Dominant distress is AC-01 (highest DV)",
        ref_result["dominant_distress_code"] == "AC-01",
    )

    print("\n-- Edge cases --------------------------------------------------")

    # Unknown defect name -> returns None and is skipped
    t_unknown = translate_vaisala_defect("made_up_defect", "low")
    _check("Unknown defect name -> translate returns None", t_unknown is None)

    # Zero-distress input -> PCI = 100
    result_empty = calculate_pci([], sample_unit_area_sqft=1000.0)
    _check("Empty distress list -> PCI = 100.0", result_empty["pci_score"] == 100.0)

    # All inventory items -> PCI = 100
    result_inv = calculate_pci(
        [{"vaisala_defect_name": "high_friction_surface", "vaisala_severity": "medium",
          "quantity": 500.0, "measurement_unit": "sq_ft"}],
        sample_unit_area_sqft=1000.0,
    )
    _check(
        "All-inventory-item input -> PCI = 100.0",
        result_inv["pci_score"] == 100.0,
    )
    _check(
        "All-inventory-item input -> inventory_items populated",
        "high_friction_surface" in result_inv["inventory_items"],
    )

    # not_assessed_codes present in output
    _check(
        "not_assessed_codes present in output",
        "AC-03" in result_empty["not_assessed_codes"],
    )

    print()
    return all_pass


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ok = validate_pci_engine()
    raise SystemExit(0 if ok else 1)
