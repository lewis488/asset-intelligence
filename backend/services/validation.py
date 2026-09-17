"""
Schema validation engine for dataset uploads.

Runs before any data is written to the database.
Returns a structured ValidationResult with errors (blocking) and
warnings/info (non-blocking).
"""
import io
import logging
import os
import tempfile
import zipfile
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from backend.dataset_schemas import ColumnSpec, DatasetSchema

logger = logging.getLogger(__name__)


# ── Result types ─────────────────────────────────────────────────────────────


@dataclass
class ValidationResult:
    passed: bool
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    info: list = field(default_factory=list)
    detected_survey_years: list = field(default_factory=list)
    row_count: int = 0
    estimated_nsg_count: int = 0

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "detected_survey_years": self.detected_survey_years,
            "row_count": self.row_count,
            "estimated_nsg_count": self.estimated_nsg_count,
        }


# ── File reading helpers ──────────────────────────────────────────────────────


def read_tabular_for_validation(content: bytes) -> pd.DataFrame:
    """Read bytes (Excel or CSV) into a DataFrame with uppercase column names."""
    try:
        df = pd.read_excel(io.BytesIO(content), header=0, dtype=object, engine="openpyxl")
    except Exception:
        try:
            df = pd.read_csv(io.BytesIO(content), dtype=object)
        except Exception as exc:
            raise ValueError(f"Cannot read file as Excel or CSV: {exc}") from exc
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df


def read_network_for_validation(content: bytes, fname: str) -> pd.DataFrame:
    """
    Read a network file (GeoPackage or zipped shapefile) into a plain DataFrame
    for column validation. Geometry column is dropped. First 100 rows only.
    """
    is_zip = fname.lower().endswith(".zip")
    suffix = ".zip" if is_zip else ".gpkg"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if is_zip:
            import geopandas as gpd
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(tmp_path) as zf:
                    zf.extractall(tmpdir)
                shp_files = [f for f in os.listdir(tmpdir) if f.lower().endswith(".shp")]
                if not shp_files:
                    return pd.DataFrame()
                gdf = gpd.read_file(os.path.join(tmpdir, shp_files[0]))
                df = pd.DataFrame({c: gdf[c] for c in gdf.columns if c.lower() != "geometry"})
                df.columns = [c.upper() for c in df.columns]
                return df.head(100)
        else:
            # GeoPackage: read attribute data via sqlite3 (no geometry load)
            import sqlite3
            conn = sqlite3.connect(tmp_path)
            cur = conn.cursor()
            try:
                cur.execute("SELECT table_name FROM gpkg_contents WHERE data_type='features'")
                layers = [r[0] for r in cur.fetchall()]
            except Exception:
                layers = []
            layer = "Road_Network" if "Road_Network" in layers else (layers[0] if layers else None)
            if not layer:
                conn.close()
                return pd.DataFrame()
            cur.execute(f'PRAGMA table_info("{layer}")')
            cols_info = cur.fetchall()
            # Exclude geometry/blob columns
            data_cols = [
                r[1] for r in cols_info
                if r[1].lower() not in ("geom", "geometry")
                and r[2].upper() not in ("BLOB", "POINT", "LINESTRING", "POLYGON",
                                          "MULTILINESTRING", "MULTIPOLYGON", "GEOMETRY")
            ]
            if not data_cols:
                conn.close()
                return pd.DataFrame()
            quoted = ", ".join(f'"{c}"' for c in data_cols)
            cur.execute(f'SELECT {quoted} FROM "{layer}" LIMIT 100')
            rows = cur.fetchall()
            conn.close()
            return pd.DataFrame(rows, columns=[c.upper() for c in data_cols])
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ── Validator ─────────────────────────────────────────────────────────────────


class DatasetValidator:
    """
    Validates a DataFrame against a DatasetSchema before ingestion.

    Call validate(df, schema) where df has already been uppercased
    (or will be uppercased internally). Returns a ValidationResult.
    """

    def validate(self, df: pd.DataFrame, schema: DatasetSchema) -> ValidationResult:
        errors: list[dict] = []
        warnings: list[dict] = []
        info: list[dict] = []

        # Work on a copy with uppercase column names
        df = df.copy()
        df.columns = [str(c).strip().upper() for c in df.columns]
        upper_cols: set[str] = set(df.columns)

        row_count = len(df)

        # ── Column checks ─────────────────────────────────────────────────────
        # col_map: canonical_name → actual_column_name_in_df
        col_map: dict[str, str] = {}

        for col_spec in schema.columns:
            found, is_alias = self._find_column(upper_cols, col_spec)

            if found:
                col_map[col_spec.canonical] = found
                if is_alias:
                    info.append({
                        "level": "info",
                        "column": col_spec.canonical,
                        "message": f"Column '{found}' mapped to '{col_spec.canonical}'",
                    })
            elif col_spec.required:
                aliases_str = ", ".join(col_spec.aliases)
                available = ", ".join(sorted(upper_cols)[:15])
                errors.append({
                    "level": "error",
                    "column": col_spec.canonical,
                    "message": (
                        f"Column '{col_spec.canonical}' not found. "
                        f"Expected one of: {aliases_str}. "
                        f"Available columns: {available}"
                    ),
                })

        # ── Range checks ──────────────────────────────────────────────────────
        for col_spec in schema.columns:
            if col_spec.canonical not in col_map:
                continue
            if col_spec.valid_range is None or col_spec.dtype != "float":
                continue

            col_name = col_map[col_spec.canonical]
            series = pd.to_numeric(df[col_name], errors="coerce").dropna()
            if series.empty:
                continue

            col_max = float(series.max())
            col_min = float(series.min())
            range_min, range_max = col_spec.valid_range

            if col_max > range_max * 1.1:
                warnings.append({
                    "level": "warning",
                    "column": col_spec.canonical,
                    "message": (
                        f"Column '{col_spec.canonical}' max value {col_max:.1f} exceeds "
                        f"expected maximum {range_max}. Check units are correct."
                    ),
                })
            if col_min < range_min:
                warnings.append({
                    "level": "warning",
                    "column": col_spec.canonical,
                    "message": (
                        f"Column '{col_spec.canonical}' has negative values "
                        f"(min={col_min:.3f})."
                    ),
                })

        # ── Unit convention checks ────────────────────────────────────────────
        for col_spec in schema.columns:
            if col_spec.canonical not in col_map or col_spec.unit is None:
                continue

            col_name = col_map[col_spec.canonical]
            series = pd.to_numeric(df[col_name], errors="coerce").dropna()
            if series.empty:
                continue

            col_max = float(series.max())

            if col_spec.unit == "score" and col_max <= 1.0:
                warnings.append({
                    "level": "warning",
                    "column": col_spec.canonical,
                    "message": (
                        f"Column '{col_spec.canonical}' max={col_max:.3f}. "
                        f"Values look like a decimal ratio (0-1). "
                        f"Expected 0-200 range. Are values stored as a fraction?"
                    ),
                })
            elif col_spec.unit == "ratio" and col_max > 1.0:
                warnings.append({
                    "level": "warning",
                    "column": col_spec.canonical,
                    "message": (
                        f"Column '{col_spec.canonical}' max={col_max:.2f}. "
                        f"Values exceed 1.0. "
                        f"Expected range 0-1 for skid coefficient."
                    ),
                })

        # ── Survey year detection ──────────────────────────────────────────────
        detected_years: list[int] = []
        if schema.date_column and schema.date_column in col_map:
            date_col_actual = col_map[schema.date_column]
            try:
                dates = pd.to_datetime(df[date_col_actual], dayfirst=True, errors="coerce")
                years = sorted(
                    dates.dt.year.dropna().astype(int).unique().tolist()
                )
                detected_years = years
                if len(years) > 1:
                    info.append({
                        "level": "info",
                        "message": (
                            f"Multiple survey years detected: {years}. "
                            f"Each will be stored separately."
                        ),
                    })
            except Exception:
                pass

        # ── NSG format check ─────────────────────────────────────────────────
        estimated_nsg_count = 0
        if schema.nsg_column in col_map:
            nsg_col_actual = col_map[schema.nsg_column]
            nsg_series = df[nsg_col_actual].astype(str).str.strip()
            estimated_nsg_count = int(nsg_series.nunique())

            leading_zero_mask = nsg_series.str.match(r"^0\d+")
            if leading_zero_mask.any():
                sample_raw = nsg_series[leading_zero_mask].iloc[0]
                sample_stripped = sample_raw.lstrip("0") or "0"
                info.append({
                    "level": "info",
                    "message": (
                        f"NSG references will be normalised (leading zeros stripped). "
                        f"e.g. '{sample_raw}' → '{sample_stripped}'"
                    ),
                })

        # ── Row count info ────────────────────────────────────────────────────
        info.append({
            "level": "info",
            "message": (
                f"File contains {row_count} rows across "
                f"approximately {estimated_nsg_count} unique NSGs"
            ),
        })

        passed = len(errors) == 0

        return ValidationResult(
            passed=passed,
            errors=errors,
            warnings=warnings,
            info=info,
            detected_survey_years=detected_years,
            row_count=row_count,
            estimated_nsg_count=estimated_nsg_count,
        )

    def _find_column(
        self, upper_cols: set[str], col_spec: ColumnSpec
    ) -> tuple[Optional[str], bool]:
        """
        Returns (found_column_name, is_alias).

        is_alias=False: found directly by canonical name (uppercased).
        is_alias=True:  found via an alias that differs from canonical.
        """
        canonical_u = col_spec.canonical.upper()
        if canonical_u in upper_cols:
            return canonical_u, False
        for alias in col_spec.aliases:
            alias_u = alias.upper()
            if alias_u in upper_cols and alias_u != canonical_u:
                return alias_u, True
        return None, False
