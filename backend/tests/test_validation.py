"""
Validation engine tests — run without database.

Tests verify the DatasetValidator against synthetic DataFrames.
No data is written anywhere; these are pure unit tests.
"""
import pandas as pd
import pytest

from dataset_schemas import SCANNER_RAW_SCHEMA
from services.validation import DatasetValidator

validator = DatasetValidator()


def _make_scanner_df(**overrides) -> pd.DataFrame:
    """Minimal valid WSCC SCANNER raw DataFrame."""
    data = {
        "NSG":           ["1234567", "7654321", "9876543"],
        "CI_VALUE":      [45.0, 82.0, 31.5],
        "SURVEY_DATE":   ["01/01/2024", "15/06/2024", "20/09/2024"],
        "OFFSET":        [-5.0, 5.0, -5.0],
        "ROAD_NAME":     ["Test Road", "Test Road", "Test Road"],
        "SURVEY_NUMBER": ["SN001", "SN001", "SN001"],
    }
    data.update(overrides)
    return pd.DataFrame(data)


# ── Test 1: Valid WSCC SCANNER file ──────────────────────────────────────────

def test_valid_scanner_file():
    """
    A proper WSCC Confirm SCANNER export should pass cleanly:
    no errors, no warnings.
    """
    df = _make_scanner_df()
    result = validator.validate(df, SCANNER_RAW_SCHEMA)

    print(f"\nTest 1 — Valid WSCC SCANNER file")
    print(f"  passed          : {result.passed}")
    print(f"  errors          : {len(result.errors)}")
    print(f"  warnings        : {len(result.warnings)}")
    print(f"  detected years  : {result.detected_survey_years}")
    print(f"  row count       : {result.row_count}")
    print(f"  nsg count       : {result.estimated_nsg_count}")
    for m in result.info:
        print(f"  info            : {m['message']}")

    assert result.passed is True, f"Expected passed=True, got errors: {result.errors}"
    assert len(result.errors) == 0, f"Expected 0 errors, got: {result.errors}"
    assert len(result.warnings) == 0, f"Expected 0 warnings, got: {result.warnings}"
    assert result.detected_survey_years == [2024]
    assert result.row_count == 3
    assert result.estimated_nsg_count == 3


# ── Test 2: Wrong units — decimal CI values ───────────────────────────────────

def test_decimal_ci_values_triggers_warning():
    """
    CI_VALUE with max <= 1.0 should trigger a 'decimal ratio' warning.
    Upload should still be allowed (passed=True), just with a warning.
    """
    df = _make_scanner_df(CI_VALUE=[0.45, 0.82, 0.31])

    result = validator.validate(df, SCANNER_RAW_SCHEMA)

    print(f"\nTest 2 — Wrong units (decimal CI values, max=0.82)")
    print(f"  passed          : {result.passed}")
    print(f"  errors          : {len(result.errors)}")
    print(f"  warnings        : {len(result.warnings)}")
    for w in result.warnings:
        print(f"  warning         : {w['message']}")

    assert result.passed is True, "Warning should not block upload"
    assert len(result.errors) == 0
    assert len(result.warnings) == 1, f"Expected exactly 1 warning, got: {result.warnings}"
    assert "decimal ratio" in result.warnings[0]["message"].lower(), \
        f"Warning should mention 'decimal ratio', got: {result.warnings[0]['message']}"
    assert result.warnings[0]["column"] == "ci_value"


# ── Test 3: Missing required column ──────────────────────────────────────────

def test_missing_nsg_column_blocks_upload():
    """
    A file without any NSG column (no NSG, NSGNO, USRN, NSG_REF)
    should fail validation and block ingestion.
    """
    df = _make_scanner_df()
    df = df.drop(columns=["NSG"])  # remove the NSG column

    result = validator.validate(df, SCANNER_RAW_SCHEMA)

    print(f"\nTest 3 — Missing NSG column")
    print(f"  passed          : {result.passed}")
    print(f"  errors          : {len(result.errors)}")
    for e in result.errors:
        print(f"  error           : {e['message']}")

    assert result.passed is False, "Missing NSG column should fail validation"
    assert len(result.errors) == 1, f"Expected exactly 1 error, got: {result.errors}"
    assert result.errors[0]["column"] == "nsg"
    assert "nsg" in result.errors[0]["message"].lower()


# ── Test 4: Multi-year file ───────────────────────────────────────────────────

def test_multi_year_file_detected():
    """
    A file spanning 2023 and 2024 should pass with an info message
    that lists both years.
    """
    df = pd.DataFrame({
        "NSG":           ["1234567", "7654321"],
        "CI_VALUE":      [45.0, 82.0],
        "SURVEY_DATE":   ["01/06/2023", "15/06/2024"],
        "OFFSET":        [-5.0, 5.0],
        "ROAD_NAME":     ["Test Road", "Test Road"],
        "SURVEY_NUMBER": ["SN001", "SN001"],
    })

    result = validator.validate(df, SCANNER_RAW_SCHEMA)

    print(f"\nTest 4 — Multi-year file (2023 + 2024)")
    print(f"  passed          : {result.passed}")
    print(f"  errors          : {len(result.errors)}")
    print(f"  warnings        : {len(result.warnings)}")
    print(f"  detected years  : {result.detected_survey_years}")
    for m in result.info:
        print(f"  info            : {m['message']}")

    assert result.passed is True
    assert len(result.errors) == 0
    assert result.detected_survey_years == [2023, 2024], \
        f"Expected [2023, 2024], got: {result.detected_survey_years}"

    multi_year_info = [m for m in result.info if "2023" in m.get("message", "") and "2024" in m.get("message", "")]
    assert len(multi_year_info) >= 1, \
        f"Expected info message about multiple years, got info: {result.info}"


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_valid_scanner_file,
        test_decimal_ci_values_triggers_warning,
        test_missing_nsg_column_blocks_upload,
        test_multi_year_file_detected,
    ]
    passed_count = 0
    failed = []
    for t in tests:
        try:
            t()
            passed_count += 1
            print(f"  PASS")
        except AssertionError as e:
            failed.append((t.__name__, str(e)))
            print(f"  FAIL: {e}")

    print(f"\n{'='*55}")
    print(f"Results: {passed_count}/{len(tests)} passed")
    if failed:
        print("Failures:")
        for name, msg in failed:
            print(f"  {name}: {msg}")
    else:
        print("All tests passed.")
