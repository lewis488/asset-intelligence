"""
Synthetic-data validation for the three raw Confirm parsers.
Run from the asset-intelligence directory:
    .venv\Scripts\python -m backend.tests.test_raw_parsers

Expected outputs are calculated below for manual verification.
"""
import io
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import pandas as pd
from backend.services.ingestion import parse_scanner_raw, parse_cvi_raw, parse_scrim_raw


def make_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode()


# ── SCANNER test ──────────────────────────────────────────────────────────────
# NSG 4700123, 5 nearside rows (OFFSET=-5), survey 01/06/2024
# CI values: 110(Red), 85(Amber), 35(Green), 95(Amber), 20(Green)
#
# Expected:
#   total_length_m = 50  (5 rows × 10m)
#   avg_ci         = 69.0  ((110+85+35+95+20)/5)
#   red_pct        = 20.0  (1/5)
#   amber_pct      = 40.0  (2/5)
#   green_pct      = 40.0  (2/5)
#   max_ci         = 110
#   min_ci         = 20
#   rci_band       = 'Red'
#   offset_direction = 'nearside'

scanner_df = pd.DataFrame({
    "NSG": ["4700123"] * 5,
    "FEATURE_ID": [f"F{i}" for i in range(5)],
    "ROAD_NAME": ["Test Road"] * 5,
    "START_CHAINAGE": [i * 10 for i in range(5)],
    "END_CHAINAGE": [(i + 1) * 10 for i in range(5)],
    "OFFSET": [-5] * 5,
    "FEATURE_GROUP": ["CARRIAGEWAY"] * 5,
    "LANE": ["CL1"] * 5,
    "OBSERVATION": [""] * 5,
    "CI_VALUE": [110, 85, 35, 95, 20],
    "SURVEY_NUMBER": ["SV-2024-001"] * 5,
    "SURVEY_DATE": ["01/06/2024 09:00"] * 5,
})

print("=" * 60)
print("SCANNER RAW PARSER TEST")
print("=" * 60)
scanner_results = parse_scanner_raw(make_csv(scanner_df), "test_scanner.csv")
r = scanner_results[0]
print(f"  nsg_ref:          {r['nsg_ref']}")
print(f"  survey_year:      {r['survey_year']}")
print(f"  offset_direction: {r['offset_direction']}")
print(f"  total_length_m:   {r['total_length_m']}  (expected 50.0)")
print(f"  avg_ci:           {r['avg_ci']:.4f}  (expected 69.0000)")
print(f"  red_pct:          {r['red_pct']:.4f}  (expected 20.0000)")
print(f"  amber_pct:        {r['amber_pct']:.4f}  (expected 40.0000)")
print(f"  green_pct:        {r['green_pct']:.4f}  (expected 40.0000)")
print(f"  max_ci:           {r['max_ci']}  (expected 110)")
print(f"  min_ci:           {r['min_ci']}  (expected 20)")
print(f"  rci_band:         {r['rci_band']}  (expected Red)")
print(f"  survey_number:    {r['survey_number']}")
print(f"  unmapped_columns: {r['_unmapped_columns']}")

assert r["total_length_m"] == 50.0, f"FAIL total_length_m: {r['total_length_m']}"
assert abs(r["avg_ci"] - 69.0) < 0.001, f"FAIL avg_ci: {r['avg_ci']}"
assert abs(r["red_pct"] - 20.0) < 0.001, f"FAIL red_pct: {r['red_pct']}"
assert abs(r["amber_pct"] - 40.0) < 0.001, f"FAIL amber_pct: {r['amber_pct']}"
assert abs(r["green_pct"] - 40.0) < 0.001, f"FAIL green_pct: {r['green_pct']}"
assert r["max_ci"] == 110.0, f"FAIL max_ci: {r['max_ci']}"
assert r["min_ci"] == 20.0, f"FAIL min_ci: {r['min_ci']}"
assert r["rci_band"] == "Red", f"FAIL rci_band: {r['rci_band']}"
assert r["offset_direction"] == "nearside", f"FAIL offset_direction: {r['offset_direction']}"
print("  PASS: All SCANNER assertions passed\n")


# ── CVI test ──────────────────────────────────────────────────────────────────
# NSG 4700456, 4 rows, survey 15/07/2023
# SECTIONLEN: 50, 100, 75, 25  → total = 250
# CI_STRUC:   70,  90,  80,  60   max=90  → flagged (>=85)
# CI_WCRSE:   50,  65,  55,  40   max=65  → flagged (>=60)
# CI_EDGE:    30,  55,  45,  25   max=55  → flagged (>=50)
# CI_OVRLL:   60,  75,  65,  50
#
# Expected:
#   total_length_m    = 250
#   avg_ci_overall    = (60×50 + 75×100 + 65×75 + 50×25) / 250 = 16625/250 = 66.5
#   max_ci_structural = 90  → structural_flagged = True
#   max_ci_edge       = 55  → edge_flagged = True
#   max_ci_wearingcourse = 65 → wearingcourse_flagged = True
#   any_flagged       = True
#   pct_length_structural_flagged = 100/250*100 = 40.0  (only row 1: CI_STRUC=90)
#   pct_length_edge_flagged       = 100/250*100 = 40.0  (only row 1: CI_EDGE=55)
#   pct_length_wc_flagged         = 100/250*100 = 40.0  (only row 1: CI_WCRSE=65)

cvi_df = pd.DataFrame({
    "NSG": ["4700456"] * 4,
    "FEATURE_ID": [f"C{i}" for i in range(4)],
    "ROAD_NAME": ["Unclassified Lane"] * 4,
    "START_CHAINAGE": [0, 50, 150, 225],
    "END_CHAINAGE": [50, 150, 225, 250],
    "CI_STRUC": [70, 90, 80, 60],
    "CI_WCRSE": [50, 65, 55, 40],
    "CI_EDGE": [30, 55, 45, 25],
    "CI_OVRLL": [60, 75, 65, 50],
    "PARISH": ["Testville"] * 4,
    "SECTIONLEN": [50, 100, 75, 25],
    "SURVEY_NUMBER": ["CVI-2023-001"] * 4,
    "SURVEY_DATE": ["15/07/2023 10:00"] * 4,
    "SURVEY_NAME": ["CVI 2023-24 REV1 BVPI"] * 4,
    "OFFSET": [0] * 4,
})

print("=" * 60)
print("CVI RAW PARSER TEST")
print("=" * 60)
cvi_results = parse_cvi_raw(make_csv(cvi_df), "test_cvi.csv")
r = cvi_results[0]
print(f"  nsg_ref:                       {r['nsg_ref']}")
print(f"  survey_year:                   {r['survey_year']}")
print(f"  survey_name:                   {r['survey_name']}")
print(f"  total_length_m:                {r['total_length_m']}  (expected 250.0)")
print(f"  avg_ci_overall:                {r['avg_ci_overall']:.4f}  (expected 66.5000)")
print(f"  max_ci_structural:             {r['max_ci_structural']}  (expected 90)")
print(f"  max_ci_edge:                   {r['max_ci_edge']}  (expected 55)")
print(f"  max_ci_wearingcourse:          {r['max_ci_wearingcourse']}  (expected 65)")
print(f"  structural_flagged:            {r['structural_flagged']}  (expected True)")
print(f"  edge_flagged:                  {r['edge_flagged']}  (expected True)")
print(f"  wearingcourse_flagged:         {r['wearingcourse_flagged']}  (expected True)")
print(f"  any_flagged:                   {r['any_flagged']}  (expected True)")
print(f"  pct_length_structural_flagged: {r['pct_length_structural_flagged']:.4f}  (expected 40.0000)")
print(f"  pct_length_edge_flagged:       {r['pct_length_edge_flagged']:.4f}  (expected 40.0000)")
print(f"  pct_length_wc_flagged:         {r['pct_length_wc_flagged']:.4f}  (expected 40.0000)")
print(f"  unmapped_columns:              {r['_unmapped_columns']}")

assert r["total_length_m"] == 250.0, f"FAIL total_length_m: {r['total_length_m']}"
assert abs(r["avg_ci_overall"] - 66.5) < 0.001, f"FAIL avg_ci_overall: {r['avg_ci_overall']}"
assert r["max_ci_structural"] == 90.0, f"FAIL max_ci_structural: {r['max_ci_structural']}"
assert r["max_ci_edge"] == 55.0, f"FAIL max_ci_edge: {r['max_ci_edge']}"
assert r["max_ci_wearingcourse"] == 65.0, f"FAIL max_ci_wearingcourse: {r['max_ci_wearingcourse']}"
assert r["structural_flagged"] is True, f"FAIL structural_flagged: {r['structural_flagged']}"
assert r["edge_flagged"] is True, f"FAIL edge_flagged: {r['edge_flagged']}"
assert r["wearingcourse_flagged"] is True, f"FAIL wearingcourse_flagged: {r['wearingcourse_flagged']}"
assert r["any_flagged"] is True, f"FAIL any_flagged: {r['any_flagged']}"
assert abs(r["pct_length_structural_flagged"] - 40.0) < 0.001, f"FAIL pct_struct: {r['pct_length_structural_flagged']}"
assert abs(r["pct_length_edge_flagged"] - 40.0) < 0.001, f"FAIL pct_edge: {r['pct_length_edge_flagged']}"
assert abs(r["pct_length_wc_flagged"] - 40.0) < 0.001, f"FAIL pct_wc: {r['pct_length_wc_flagged']}"
print("  PASS: All CVI assertions passed\n")


# ── SCRIM test ────────────────────────────────────────────────────────────────
# NSG 4700789, 6 rows, survey 10/08/2023
# SFC:  0.45, 0.38, 0.52, 0.30, 0.0 (no reading), 0.41
# SFCT: 0.45, 0.45, 0.45, 0.45, 0.45, 0.45
# XDIF: 0.00, -0.07, 0.07, -0.15, 0.00, -0.04
# ILCT: A,    A,     A,    A,     A,    B
#
# Expected:
#   total_sections   = 6
#   dominant_ilct    = 'A'
#   sfct_threshold   = 0.45
#   mean_sfc         = (0.45+0.38+0.52+0.30+0.41)/5 = 2.06/5 = 0.412
#   min_sfc          = 0.30
#   sections_below_il = 3  (XDIF < 0: rows 1, 3, 5)
#   pct_below_il     = 50.0
#   safety_flagged   = True
#   worst_xdif       = -0.15

scrim_df = pd.DataFrame({
    "NSG": ["4700789"] * 6,
    "FEATURE_ID": [f"S{i}" for i in range(6)],
    "ROAD_NAME": ["Skid Test Road"] * 6,
    "PARISH": ["Griptown"] * 6,
    "ILCT": ["A", "A", "A", "A", "A", "B"],
    "SFC": [0.45, 0.38, 0.52, 0.30, 0.0, 0.41],
    "SFCT": [0.45, 0.45, 0.45, 0.45, 0.45, 0.45],
    "XDIF": [0.00, -0.07, 0.07, -0.15, 0.00, -0.04],
    "STARTCHAIN": [i * 10 for i in range(6)],
    "ENDCHAIN": [(i + 1) * 10 for i in range(6)],
    "XSP_CODE": ["CL1"] * 6,
    "OFFSET": [-5] * 6,
    "SURVEYNUMB": ["SCRIM-2023-001"] * 6,
    "SURVEYDATE": ["10/08/2023 08:30"] * 6,
    "SURVEY_NAME": ["SCRIM 2023"] * 6,
})

print("=" * 60)
print("SCRIM RAW PARSER TEST")
print("=" * 60)
scrim_results = parse_scrim_raw(make_csv(scrim_df), "test_scrim.csv")
r = scrim_results[0]
print(f"  nsg_ref:           {r['nsg_ref']}")
print(f"  survey_year:       {r['survey_year']}")
print(f"  survey_name:       {r['survey_name']}")
print(f"  total_sections:    {r['total_sections']}  (expected 6)")
print(f"  dominant_ilct:     {r['dominant_ilct']}  (expected A)")
print(f"  sfct_threshold:    {r['sfct_threshold']}  (expected 0.45)")
print(f"  mean_sfc:          {r['mean_sfc']:.4f}  (expected 0.4120)")
print(f"  min_sfc:           {r['min_sfc']}  (expected 0.3)")
print(f"  sections_below_il: {r['sections_below_il']}  (expected 3)")
print(f"  pct_below_il:      {r['pct_below_il']:.4f}  (expected 50.0000)")
print(f"  safety_flagged:    {r['safety_flagged']}  (expected True)")
print(f"  worst_xdif:        {r['worst_xdif']}  (expected -0.15)")
print(f"  unmapped_columns:  {r['_unmapped_columns']}")

assert r["total_sections"] == 6, f"FAIL total_sections: {r['total_sections']}"
assert r["dominant_ilct"] == "A", f"FAIL dominant_ilct: {r['dominant_ilct']}"
assert abs(r["sfct_threshold"] - 0.45) < 0.001, f"FAIL sfct_threshold: {r['sfct_threshold']}"
assert abs(r["mean_sfc"] - 0.412) < 0.001, f"FAIL mean_sfc: {r['mean_sfc']}"
assert abs(r["min_sfc"] - 0.30) < 0.001, f"FAIL min_sfc: {r['min_sfc']}"
assert r["sections_below_il"] == 3, f"FAIL sections_below_il: {r['sections_below_il']}"
assert abs(r["pct_below_il"] - 50.0) < 0.001, f"FAIL pct_below_il: {r['pct_below_il']}"
assert r["safety_flagged"] is True, f"FAIL safety_flagged: {r['safety_flagged']}"
assert abs(r["worst_xdif"] - (-0.15)) < 0.001, f"FAIL worst_xdif: {r['worst_xdif']}"
print("  PASS: All SCRIM assertions passed\n")

print("=" * 60)
print("ALL TESTS PASSED")
print("=" * 60)
