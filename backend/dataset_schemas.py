"""
Schema registry for all dataset upload types.

Each schema declares required/optional columns with canonical names + aliases,
data types, valid ranges, unit conventions, and the key columns used for
year extraction and NSG normalisation.

Canonical names are lowercase display identifiers.
Aliases are uppercase — what the actual file columns will be named.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ColumnSpec:
    canonical: str
    aliases: list[str]          # uppercase — what the actual file column may be called
    dtype: str = "string"       # 'string', 'float', 'date'
    required: bool = True
    valid_range: Optional[tuple] = None   # (min, max) inclusive for floats
    unit: Optional[str] = None           # 'score', 'ratio' — drives unit convention checks
    date_formats: Optional[list] = None


@dataclass
class DatasetSchema:
    name: str
    columns: list[ColumnSpec]
    date_column: Optional[str] = None   # canonical name of the date column
    nsg_column: str = "nsg"             # canonical name of the NSG column


# ── SCANNER RAW ───────────────────────────────────────────────────────────────
# Direct Confirm SCANNER export (10m interval rows).
# Aggregated to one record per (NSG, survey_year, offset_direction).

SCANNER_RAW_SCHEMA = DatasetSchema(
    name="SCANNER_RAW",
    date_column="survey_date",
    nsg_column="nsg",
    columns=[
        ColumnSpec(
            canonical="nsg",
            aliases=["NSG", "NSGNO", "USRN", "NSG_REF"],
            dtype="string",
        ),
        ColumnSpec(
            canonical="ci_value",
            aliases=["CI_VALUE", "RCI", "RCI_VALUE", "CONDITION_INDEX"],
            dtype="float",
            valid_range=(0, 200),
            unit="score",
        ),
        ColumnSpec(
            canonical="survey_date",
            aliases=["SURVEY_DATE", "SURVEYDATE", "DATE"],
            dtype="date",
            date_formats=["%d/%m/%Y %H:%M", "%d/%m/%Y"],
        ),
        ColumnSpec(
            canonical="survey_number",
            aliases=["SURVEY_NUMBER", "SURVEYNUMB"],
            required=False,
        ),
        ColumnSpec(
            canonical="offset",
            aliases=["OFFSET"],
            dtype="float",
            required=False,
        ),
    ],
)


# ── CVI RAW ───────────────────────────────────────────────────────────────────
# Direct Confirm CVI export (variable-length sections).
# Aggregated to one record per (NSG, survey_year).

CVI_RAW_SCHEMA = DatasetSchema(
    name="CVI_RAW",
    date_column="survey_date",
    nsg_column="nsg",
    columns=[
        ColumnSpec(
            canonical="nsg",
            aliases=["NSG", "NSGNO", "USRN"],
            dtype="string",
        ),
        ColumnSpec(
            canonical="ci_struc",
            aliases=["CI_STRUC", "STRUCTURAL_CI", "CI_STRUCTURAL"],
            dtype="float",
            valid_range=(0, 200),
            unit="score",
            required=False,
        ),
        ColumnSpec(
            canonical="ci_wcrse",
            aliases=["CI_WCRSE", "CI_WEARINGCOURSE", "WEARING_COURSE_CI"],
            dtype="float",
            valid_range=(0, 200),
            unit="score",
            required=False,
        ),
        ColumnSpec(
            canonical="ci_edge",
            aliases=["CI_EDGE", "EDGE_CI"],
            dtype="float",
            valid_range=(0, 200),
            unit="score",
            required=False,
        ),
        ColumnSpec(
            canonical="ci_ovrll",
            aliases=["CI_OVRLL", "CI_OVERALL", "OVERALL_CI"],
            dtype="float",
            valid_range=(0, 200),
            unit="score",
            required=False,
        ),
        ColumnSpec(
            canonical="sectionlen",
            aliases=["SECTIONLEN", "SECTION_LENGTH", "LENGTH_M"],
            dtype="float",
            valid_range=(0, 5000),
        ),
        ColumnSpec(
            canonical="survey_date",
            aliases=["SURVEY_DATE", "SURVEYDATE", "DATE"],
            dtype="date",
            date_formats=["%d/%m/%Y %H:%M", "%d/%m/%Y"],
        ),
        ColumnSpec(
            canonical="survey_name",
            aliases=["SURVEY_NAME"],
            required=False,
        ),
    ],
)


# ── SCRIM RAW ─────────────────────────────────────────────────────────────────
# Direct Confirm SCRIM export (10m interval rows, MSSC averaged).
# Aggregated to one record per (NSG, survey_year).
# SFC=0 rows excluded (zero = no reading, not actual zero skid resistance).

SCRIM_RAW_SCHEMA = DatasetSchema(
    name="SCRIM_RAW",
    date_column="survey_date",
    nsg_column="nsg",
    columns=[
        ColumnSpec(
            canonical="nsg",
            aliases=["NSG", "NSGNO", "USRN"],
            dtype="string",
        ),
        ColumnSpec(
            canonical="sfc",
            aliases=["SFC", "SKID_FRICTION_COEFF"],
            dtype="float",
            valid_range=(0, 1),
            unit="ratio",
        ),
        ColumnSpec(
            canonical="sfct",
            aliases=["SFCT", "SFC_THRESHOLD", "IL_VALUE", "INVESTIGATORY_LEVEL"],
            dtype="float",
            valid_range=(0, 1),
            unit="ratio",
        ),
        ColumnSpec(
            canonical="xdif",
            aliases=["XDIF", "SFC_MINUS_IL", "MARGIN"],
            dtype="float",
        ),
        ColumnSpec(
            canonical="ilct",
            aliases=["ILCT", "IL_CATEGORY", "SITE_CATEGORY"],
            required=False,
        ),
        ColumnSpec(
            canonical="survey_date",
            aliases=["SURVEYDATE", "SURVEY_DATE"],
            dtype="date",
            date_formats=["%d/%m/%Y %H:%M", "%d/%m/%Y"],
        ),
        ColumnSpec(
            canonical="survey_name",
            aliases=["SURVEY_NAME"],
            required=False,
        ),
    ],
)


# ── REACTIVE RAW ──────────────────────────────────────────────────────────────
# Direct Confirm reactive jobs export.
# Filtered to condition-relevant types and completed statuses.

REACTIVE_RAW_SCHEMA = DatasetSchema(
    name="REACTIVE_RAW",
    date_column="job_entry_date",
    nsg_column="nsg",
    columns=[
        ColumnSpec(
            canonical="nsg",
            aliases=["SITE_CODE", "NSG", "USRN", "SITE_REF"],
            dtype="string",
        ),
        ColumnSpec(
            canonical="site_name",
            aliases=["SITE_NAME", "ROAD_NAME", "LOCATION"],
            required=False,
        ),
        ColumnSpec(
            canonical="job_entry_date",
            aliases=["JOB_ENTRY_DATE", "ENTRY_DATE", "DATE_RAISED"],
            dtype="date",
        ),
        ColumnSpec(
            canonical="actual_comp_date",
            aliases=["ACTUAL_COMP_DATE", "COMPLETION_DATE", "COMP_DATE"],
            dtype="date",
            required=False,
        ),
        ColumnSpec(
            canonical="priority_name",
            aliases=["PRIORITY_NAME", "PRIORITY", "PRIORITY_CODE"],
            required=False,
        ),
        ColumnSpec(
            canonical="job_type_name",
            aliases=["JOB_TYPE_NAME", "JOB_TYPE", "DEFECT_TYPE"],
            required=False,
        ),
        ColumnSpec(
            canonical="status_name",
            aliases=["STATUS_NAME", "STATUS"],
            required=False,
        ),
        ColumnSpec(
            canonical="job_number",
            aliases=["JOB_NUMBER", "JOB_NO", "JOB_REF"],
            required=False,
        ),
    ],
)


# ── NETWORK SHP ───────────────────────────────────────────────────────────────
# WSCC road network master register (.gpkg or .zip containing .shp).
# Filtered to ABCD road classes + WSCC ownership.
# Reprojected from EPSG:27700 to EPSG:4326.

NETWORK_SHP_SCHEMA = DatasetSchema(
    name="NETWORK_SHP",
    date_column=None,   # network register has no survey date
    nsg_column="nsg",
    columns=[
        ColumnSpec(
            canonical="nsg",
            aliases=["NSGNO", "NSG", "USRN", "NSG_REF"],
            dtype="string",
        ),
        ColumnSpec(
            canonical="road_class",
            aliases=["CLASS", "ROAD_CLASS", "RD_CLASS", "HIERARCHY"],
            dtype="string",
        ),
        ColumnSpec(
            canonical="road_name",
            aliases=["ROADNAME", "ROAD_NAME", "NAME"],
            required=False,
        ),
        ColumnSpec(
            canonical="length_m",
            aliases=["CWLENGTH", "LENGTH_M", "CARRIAGEWAY_LENGTH", "LEN"],
            dtype="float",
            valid_range=(0, 10000),
        ),
        ColumnSpec(
            canonical="width_m",
            aliases=["CWAVGWDTH", "AVG_WIDTH", "WIDTH"],
            dtype="float",
            valid_range=(0, 50),
            required=False,
        ),
        ColumnSpec(
            canonical="area_m2",
            aliases=["CWAREA", "AREA", "CARRIAGE_AREA"],
            dtype="float",
            required=False,
        ),
        ColumnSpec(
            canonical="parish",
            aliases=["PARISH"],
            required=False,
        ),
        ColumnSpec(
            canonical="district",
            aliases=["DISTRICT"],
            required=False,
        ),
        ColumnSpec(
            canonical="urban_rural",
            aliases=["URBANRURAL", "URBAN_RURAL"],
            required=False,
        ),
    ],
)
