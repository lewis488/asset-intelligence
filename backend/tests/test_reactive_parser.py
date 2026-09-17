"""
Synthetic-data validation for parse_reactive_raw().
Run from the asset-intelligence directory:
    .venv\Scripts\python -m backend.tests.test_reactive_parser

20 rows: 15 condition-relevant + complete/inspected, 5 filtered out.
Filtered: 2 footway type, 2 OOH type, 1 cancelled status.

Expected aggregates verified inline (no DB needed).
"""
import sys
import os
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import pandas as pd
from backend.services.ingestion import parse_reactive_raw


def make_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode()


# ── Synthetic data ────────────────────────────────────────────────────────────
#
# NSG1 (4700100): 4 jobs 2024 — J001-J004
#   J001 Potholes|CWAY Cat1 complete  entry 10/01/2024 comp 10/01/2024  (0 days)
#   J002 Potholes|CWAY Cat2 complete  entry 01/02/2024 comp 06/02/2024  (5 days)
#   J003 Patching|CWAY Cat4 complete  entry 15/03/2024 comp 01/04/2024  (17 days)
#   J004 Potholes|CWAY Cat1 complete  entry 01/06/2024 comp = None      (outstanding)
#
# NSG2 (4700200): 3 jobs 2024 — J005-J007
#   J005 Potholes|CWAY Cat2 complete  entry 20/01/2024 comp 22/01/2024  (2 days)
#   J006 Patching|CWAY Cat3 complete  entry 10/03/2024 comp 14/03/2024  (4 days)
#   J007 Kerb|Edge Works Cat4 complete entry 20/05/2024 comp 10/06/2024 (21 days)
#
# NSG3 (4700300): 2 jobs 2025 — J008-J009
#   J008 Potholes|CWAY Cat1 complete  entry 15/01/2025 comp 16/01/2025  (1 day)
#   J009 Verge Repairs Cat4 inspected entry 10/03/2025 comp = None      (outstanding)
#
# NSG4 (4700400): 3 jobs 2025 — J010-J012
#   J010 Patching|CWAY Cat3 inspected entry 01/02/2025 comp 07/02/2025  (6 days)
#   J011 Patching|CWAY Cat4 complete  entry 10/04/2025 comp 01/05/2025  (21 days)
#   J012 Covers|Gullies CWAY Cat3 complete entry 15/05/2025 comp 20/05/2025 (5 days)
#
# NSG5 (4700500): 3 jobs 2025 — J013-J015
#   J013 Covers|Gullies CWAY Cat2 complete entry 01/03/2025 comp 02/03/2025 (1 day)
#   J014 Potholes|CWAY Cat1 inspected entry 01/04/2025 comp = None       (outstanding)
#   J015 Patching|CWAY Cat3 complete  entry 01/05/2025 comp = None       (outstanding)
#
# FILTERED (J016-J020):
#   J016 Footway Defects     — type not in include list
#   J017 Out of Hours Emergency — type not in include list
#   J018 Potholes|CWAY / Job Cancelled — status not valid
#   J019 Footway Repairs     — type not in include list
#   J020 Footway Patching    — contains 'patching' but NOT 'patching | cway'

rows = [
    # job_number  site_code  site_name            job_entry_date  actual_comp_date  priority_name        job_type_name           status_name        district_name  locality_name  town_name   road_class  easting   northing
    ("J001", "4700100", "Test Road A",  "10/01/2024", "10/01/2024", "Cat1: 2_Hours",  "Potholes | CWAY",       "Works Complete",  "District1", "Loc1", "Town1", "A", 480000, 120000),
    ("J002", "4700100", "Test Road A",  "01/02/2024", "06/02/2024", "Cat2: 24_Hours", "Potholes | CWAY",       "Works Complete",  "District1", "Loc1", "Town1", "A", 480000, 120000),
    ("J003", "4700100", "Test Road A",  "15/03/2024", "01/04/2024", "Cat4: 28 Days",  "Patching | CWAY",       "Works Complete",  "District1", "Loc1", "Town1", "A", 480000, 120000),
    ("J004", "4700100", "Test Road A",  "01/06/2024", "",           "Cat1: 2_Hours",  "Potholes | CWAY",       "Works Complete",  "District1", "Loc1", "Town1", "A", 480000, 120000),
    ("J005", "4700200", "Test Road B",  "20/01/2024", "22/01/2024", "Cat2: 24_Hours", "Potholes | CWAY",       "Works Complete",  "District1", "Loc2", "Town2", "A", 481000, 121000),
    ("J006", "4700200", "Test Road B",  "10/03/2024", "14/03/2024", "Cat3: 5 Days",   "Patching | CWAY",       "Works Complete",  "District1", "Loc2", "Town2", "A", 481000, 121000),
    ("J007", "4700200", "Test Road B",  "20/05/2024", "10/06/2024", "Cat4: 28 Days",  "Kerb | Edge Works",     "Works Complete",  "District1", "Loc2", "Town2", "A", 481000, 121000),
    ("J008", "4700300", "Test Road C",  "15/01/2025", "16/01/2025", "Cat1: 2_Hours",  "Potholes | CWAY",       "Works Complete",  "District2", "Loc3", "Town3", "B", 482000, 122000),
    ("J009", "4700300", "Test Road C",  "10/03/2025", "",           "Cat4: 28 Days",  "Verge Repairs",         "Work Inspected",  "District2", "Loc3", "Town3", "B", 482000, 122000),
    ("J010", "4700400", "Test Road D",  "01/02/2025", "07/02/2025", "Cat3: 5 Days",   "Patching | CWAY",       "Work Inspected",  "District2", "Loc4", "Town4", "B", 483000, 123000),
    ("J011", "4700400", "Test Road D",  "10/04/2025", "01/05/2025", "Cat4: 28 Days",  "Patching | CWAY",       "Works Complete",  "District2", "Loc4", "Town4", "B", 483000, 123000),
    ("J012", "4700400", "Test Road D",  "15/05/2025", "20/05/2025", "Cat3: 5 Days",   "Covers | Gullies CWAY", "Works Complete",  "District2", "Loc4", "Town4", "B", 483000, 123000),
    ("J013", "4700500", "Test Road E",  "01/03/2025", "02/03/2025", "Cat2: 24_Hours", "Covers | Gullies CWAY", "Works Complete",  "District3", "Loc5", "Town5", "C", 484000, 124000),
    ("J014", "4700500", "Test Road E",  "01/04/2025", "",           "Cat1: 2_Hours",  "Potholes | CWAY",       "Work Inspected",  "District3", "Loc5", "Town5", "C", 484000, 124000),
    ("J015", "4700500", "Test Road E",  "01/05/2025", "",           "Cat3: 5 Days",   "Patching | CWAY",       "Works Complete",  "District3", "Loc5", "Town5", "C", 484000, 124000),
    # --- FILTERED ---
    ("J016", "4700100", "Test Road A",  "15/01/2024", "20/01/2024", "Cat3: 5 Days",   "Footway Defects",        "Works Complete",  "District1", "Loc1", "Town1", "A", 480000, 120000),
    ("J017", "4700200", "Test Road B",  "05/02/2024", "05/02/2024", "Cat1: 2_Hours",  "Out of Hours Emergency", "Works Complete",  "District1", "Loc2", "Town2", "A", 481000, 121000),
    ("J018", "4700300", "Test Road C",  "20/02/2025", "",           "Cat1: 2_Hours",  "Potholes | CWAY",        "Job Cancelled",   "District2", "Loc3", "Town3", "B", 482000, 122000),
    ("J019", "4700400", "Test Road D",  "25/03/2025", "28/03/2025", "Cat2: 24_Hours", "Footway Repairs",        "Works Complete",  "District2", "Loc4", "Town4", "B", 483000, 123000),
    ("J020", "4700500", "Test Road E",  "10/04/2025", "15/04/2025", "Cat3: 5 Days",   "Footway Patching",       "Works Complete",  "District3", "Loc5", "Town5", "C", 484000, 124000),
]

cols = ["job_number", "site_code", "site_name", "job_entry_date", "actual_comp_date",
        "priority_name", "job_type_name", "status_name", "district_name",
        "locality_name", "town_name", "road_class", "easting", "northing"]

df = pd.DataFrame(rows, columns=cols)
csv_bytes = make_csv(df)


# ── Run parser ────────────────────────────────────────────────────────────────
print("=" * 60)
print("REACTIVE RAW PARSER TEST")
print("=" * 60)
result = parse_reactive_raw(csv_bytes, "test_reactive.csv")
records = result["records"]
filtered_out = result["filtered_out"]
breakdown = result["job_type_breakdown"]

print(f"  Total rows input:   20")
print(f"  Records kept:       {len(records)}  (expected 15)")
print(f"  Filtered out:       {filtered_out}  (expected 5)")
print(f"  Job type breakdown: {breakdown}")
print(f"  Expected:           pothole=6, patching=5, edge=2, drainage=2")
print()

# ── Assertions: filter counts ─────────────────────────────────────────────────
assert len(records) == 15, f"FAIL records kept: {len(records)}"
assert filtered_out == 5, f"FAIL filtered_out: {filtered_out}"
assert breakdown.get("pothole", 0) == 6,   f"FAIL pothole: {breakdown}"
assert breakdown.get("patching", 0) == 5,  f"FAIL patching: {breakdown}"
assert breakdown.get("edge", 0) == 2,      f"FAIL edge: {breakdown}"
assert breakdown.get("drainage", 0) == 2,  f"FAIL drainage: {breakdown}"
assert breakdown.get("other", 0) == 0,     f"FAIL other: {breakdown}"

# ── Assertions: filtered job numbers absent ───────────────────────────────────
kept_nums = {r["job_number"] for r in records}
for filtered_job in ("J016", "J017", "J018", "J019", "J020"):
    assert filtered_job not in kept_nums, f"FAIL {filtered_job} should be filtered"

# ── Assertions: job_type_category ─────────────────────────────────────────────
by_num = {r["job_number"]: r for r in records}
assert by_num["J007"]["job_type_category"] == "edge",     "FAIL J007 category"
assert by_num["J012"]["job_type_category"] == "drainage", "FAIL J012 category"
assert by_num["J009"]["job_type_category"] == "edge",     "FAIL J009 category (Verge Repairs)"
assert by_num["J013"]["job_type_category"] == "drainage", "FAIL J013 category (Gullies)"

# ── Assertions: priority_category ─────────────────────────────────────────────
assert by_num["J001"]["priority_category"] == 1, f"FAIL J001 priority: {by_num['J001']['priority_category']}"
assert by_num["J002"]["priority_category"] == 2, f"FAIL J002 priority: {by_num['J002']['priority_category']}"
assert by_num["J006"]["priority_category"] == 3, f"FAIL J006 priority: {by_num['J006']['priority_category']}"
assert by_num["J003"]["priority_category"] == 4, f"FAIL J003 priority: {by_num['J003']['priority_category']}"

print("PASS: Filter, job_type_category, priority_category assertions")
print()

# ── Manual aggregate computation ─────────────────────────────────────────────
# (mirrors _rebuild_reactive_aggregate logic, no DB needed)

def compute_aggregate(jobs: list[dict], year: int, nsg: str) -> dict:
    """Compute aggregate from a list of job dicts for one NSG/year."""
    today = datetime.utcnow().date()
    subset = [j for j in jobs if j["nsg_ref"] == nsg
              and j["job_entry_date"] is not None
              and j["job_entry_date"].year == year]

    entry_dates = [j["job_entry_date"] for j in subset if j["job_entry_date"]]
    most_recent = max(entry_dates) if entry_dates else None

    completed = [j for j in subset if j["actual_comp_date"]]
    outstanding = [j for j in subset if not j["actual_comp_date"]]

    comp_days = [
        (j["actual_comp_date"].date() - j["job_entry_date"].date()).days
        for j in completed
        if j["job_entry_date"]
        and (j["actual_comp_date"].date() - j["job_entry_date"].date()).days >= 0
    ]

    outstanding_dates = [j["job_entry_date"] for j in outstanding if j["job_entry_date"]]

    return {
        "total_jobs_raised": len(subset),
        "emergency_jobs_2hr": sum(1 for j in subset if j["priority_category"] == 1),
        "urgent_jobs_24hr":   sum(1 for j in subset if j["priority_category"] == 2),
        "jobs_5day":          sum(1 for j in subset if j["priority_category"] == 3),
        "jobs_28day":         sum(1 for j in subset if j["priority_category"] == 4),
        "pothole_count":   sum(1 for j in subset if j["job_type_category"] == "pothole"),
        "patching_count":  sum(1 for j in subset if j["job_type_category"] == "patching"),
        "edge_count":      sum(1 for j in subset if j["job_type_category"] == "edge"),
        "drainage_count":  sum(1 for j in subset if j["job_type_category"] == "drainage"),
        "jobs_completed":  len(completed),
        "jobs_outstanding": len(outstanding),
        "mean_days_to_completion": sum(comp_days) / len(comp_days) if comp_days else None,
        "most_recent_defect_date": most_recent,
        "days_since_most_recent_defect": (today - most_recent.date()).days if most_recent else None,
        "oldest_outstanding_days": (today - min(d.date() for d in outstanding_dates)).days if outstanding_dates else None,
    }


# NSG1 2024
print("=" * 60)
print("AGGREGATE: NSG1 (4700100) 2024")
print("=" * 60)
agg1 = compute_aggregate(records, 2024, "4700100")
today = datetime.utcnow().date()
expected_recent_days_nsg1 = (today - date(2024, 6, 1)).days
expected_oldest_days_nsg1 = (today - date(2024, 6, 1)).days  # only one outstanding (J004)

for k, v in agg1.items():
    print(f"  {k}: {v}")

assert agg1["total_jobs_raised"] == 4,  f"FAIL total: {agg1['total_jobs_raised']}"
assert agg1["emergency_jobs_2hr"] == 2, f"FAIL cat1: {agg1['emergency_jobs_2hr']}"
assert agg1["urgent_jobs_24hr"] == 1,   f"FAIL cat2: {agg1['urgent_jobs_24hr']}"
assert agg1["jobs_28day"] == 1,         f"FAIL cat4: {agg1['jobs_28day']}"
assert agg1["pothole_count"] == 3,      f"FAIL potholes: {agg1['pothole_count']}"
assert agg1["patching_count"] == 1,     f"FAIL patching: {agg1['patching_count']}"
assert agg1["jobs_completed"] == 3,     f"FAIL completed: {agg1['jobs_completed']}"
assert agg1["jobs_outstanding"] == 1,   f"FAIL outstanding: {agg1['jobs_outstanding']}"
assert abs(agg1["mean_days_to_completion"] - 22/3) < 0.01, \
    f"FAIL mean_days: {agg1['mean_days_to_completion']} (expected {22/3:.4f})"
assert agg1["days_since_most_recent_defect"] == expected_recent_days_nsg1, \
    f"FAIL days_since: {agg1['days_since_most_recent_defect']}"
assert agg1["oldest_outstanding_days"] == expected_oldest_days_nsg1, \
    f"FAIL oldest_outstanding: {agg1['oldest_outstanding_days']}"
print(f"  PASS: NSG1 2024 (mean_days={agg1['mean_days_to_completion']:.4f}, expected {22/3:.4f})\n")


# NSG2 2024
print("=" * 60)
print("AGGREGATE: NSG2 (4700200) 2024")
print("=" * 60)
agg2 = compute_aggregate(records, 2024, "4700200")
for k, v in agg2.items():
    print(f"  {k}: {v}")

assert agg2["total_jobs_raised"] == 3,    f"FAIL total: {agg2['total_jobs_raised']}"
assert agg2["pothole_count"] == 1,        f"FAIL pothole: {agg2['pothole_count']}"
assert agg2["patching_count"] == 1,       f"FAIL patching: {agg2['patching_count']}"
assert agg2["edge_count"] == 1,           f"FAIL edge: {agg2['edge_count']}"
assert agg2["jobs_completed"] == 3,       f"FAIL completed: {agg2['jobs_completed']}"
assert agg2["jobs_outstanding"] == 0,     f"FAIL outstanding: {agg2['jobs_outstanding']}"
assert abs(agg2["mean_days_to_completion"] - 9.0) < 0.01, \
    f"FAIL mean_days: {agg2['mean_days_to_completion']} (expected 9.0)"
assert agg2["oldest_outstanding_days"] is None, \
    f"FAIL oldest_outstanding should be None: {agg2['oldest_outstanding_days']}"
print(f"  PASS: NSG2 2024 (mean_days={agg2['mean_days_to_completion']:.4f}, expected 9.0000)\n")


# NSG5 2025 — two outstanding jobs
print("=" * 60)
print("AGGREGATE: NSG5 (4700500) 2025")
print("=" * 60)
agg5 = compute_aggregate(records, 2025, "4700500")
expected_oldest_nsg5 = (today - date(2025, 4, 1)).days  # J014 is oldest outstanding
for k, v in agg5.items():
    print(f"  {k}: {v}")

assert agg5["jobs_outstanding"] == 2,   f"FAIL outstanding: {agg5['jobs_outstanding']}"
assert agg5["jobs_completed"] == 1,     f"FAIL completed: {agg5['jobs_completed']}"
assert abs(agg5["mean_days_to_completion"] - 1.0) < 0.01, \
    f"FAIL mean_days: {agg5['mean_days_to_completion']}"
assert agg5["oldest_outstanding_days"] == expected_oldest_nsg5, \
    f"FAIL oldest_outstanding: {agg5['oldest_outstanding_days']} (expected {expected_oldest_nsg5})"
print(f"  PASS: NSG5 2025\n")


print("=" * 60)
print("ALL TESTS PASSED")
print("=" * 60)
