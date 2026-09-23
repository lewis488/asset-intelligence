"""Coverage QC matching priority_dst.html; outputs use whole percentages.

Raw Vaisala coverage is a 0–1 fraction. Explicit percent strings and numeric
values above 1 are also accepted. Missing/invalid readings remain unknown.
"""
import math
import re


def coverage_value(fields, kind):
    aliases = (f'coverage{kind}', f'{kind}coverage')
    for name, value in fields.items():
        key = re.sub(r'[^a-z0-9]', '', str(name).lower())
        if not any(alias in key for alias in aliases):
            continue
        try:
            explicit_pct = isinstance(value, str) and '%' in value
            number = float(str(value).replace('%', '').strip())
            if explicit_pct or number > 1:
                number /= 100
            return number if math.isfinite(number) and 0 <= number <= 1 else None
        except (TypeError, ValueError):
            return None
    return None


def calculate_qc(rows):
    """Rows are (length_m, raw coverage field mapping), after pass deduplication."""
    total_sum = valid_sum = total_weight = valid_weight = 0.0
    for length, fields in rows:
        if not length or not math.isfinite(length) or length <= 0:
            continue
        total = coverage_value(fields, 'total')
        valid = coverage_value(fields, 'valid')
        if total is not None:
            total_sum += total * length
            total_weight += length
        if valid is not None:
            valid_sum += valid * length
            valid_weight += length
    completeness = total_sum / total_weight if total_weight else None
    valid_avg = valid_sum / valid_weight if valid_weight else None
    reliability = (min(1, valid_avg / completeness)
                   if completeness is not None and completeness > 0 and valid_avg is not None
                   else None if completeness == 0 else valid_avg)

    def band(value):
        return None if value is None else 'High' if value >= 0.85 else 'Medium' if value >= 0.5 else 'Low'

    return {
        'qc_completeness_pct': round(completeness * 100, 6) if completeness is not None else None,
        'qc_completeness_band': band(completeness),
        'qc_reliability_pct': round(reliability * 100, 6) if reliability is not None else None,
        'qc_reliability_band': band(reliability),
    }
