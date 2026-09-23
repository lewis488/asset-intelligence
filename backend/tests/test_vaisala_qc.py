import io
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from services.vaisala_scoring import parse_raw_csv, parse_raw_xlsx
from routers.vaisala import _interval_to_section_dict, _intervals_to_100m_sections
from test_admin import api


def test_raw_qc_survives_upload_and_scaled_views():
    raw = b'SECTIONLAB,Length,From,To,Coverage (total),Coverage (valid),Filter\nA,10,0,10,0.2,0.2,\nA,30,10,40,1,0.5,Obstruction\n'
    result = parse_raw_csv(raw, 'stroud')
    section = result['sections'][0]
    assert section['qc_completeness_pct'] == pytest.approx(80)
    assert section['qc_reliability_pct'] == pytest.approx(53.125)
    assert section['qc_completeness_band'] == 'Medium'
    intervals = [SimpleNamespace(id=i, **row) for i, row in enumerate(result['intervals'])]
    assert json.loads(intervals[1].extras_json)['Filter'] == 'Obstruction'
    first = _interval_to_section_dict(intervals[0], 1)
    assert first['qc_completeness_pct'] == 20
    assert first['qc_reliability_pct'] == 100
    grouped = _intervals_to_100m_sections(intervals, 1)[0]
    assert grouped['qc_completeness_pct'] == pytest.approx(80)
    assert grouped['qc_reliability_pct'] == pytest.approx(53.125)


@pytest.mark.parametrize('total,valid,completeness,reliability,band', [
    ('85%', '68%', 85, 80, 'High'), ('50', '25', 50, 50, 'Medium'),
    ('0', '0', 0, None, 'Low'), ('', '', None, None, None),
    ('bad', '-1', None, None, None), ('20', '30', 20, 100, 'Low'),
    ('', '0.7', None, 70, None), ('0.9', '', 90, None, 'High'),
])
def test_qc_units_missing_and_boundaries(total, valid, completeness, reliability, band):
    raw = f'SECTIONLAB,Length,Coverage (total),Coverage (valid)\nA,10,{total},{valid}\n'.encode()
    section = parse_raw_csv(raw, 'stroud')['sections'][0]
    assert section['qc_completeness_pct'] == completeness
    assert section['qc_reliability_pct'] == reliability
    assert section['qc_completeness_band'] == band


def test_xlsx_fraction_coverage_and_latest_pass():
    frame = pd.DataFrame({'SECTIONLAB': ['A', 'A'], 'Length': [10, 10], 'From': [0, 0], 'To': [10, 10],
                          'Time UTC': ['2025-01-01', '2026-01-01'],
                          'coverage (TOTAL)': [0.1, 0.9], 'Coverage (valid)': [0.1, 0.45]})
    out = io.BytesIO()
    frame.to_excel(out, index=False)
    result = parse_raw_xlsx(out.getvalue(), 'stroud')
    assert result['sections'][0]['qc_completeness_pct'] == 90
    assert result['sections'][0]['qc_reliability_pct'] == 50


def test_upload_persists_qc_for_all_api_views_and_export(api):
    client, headers, _ = api
    raw = b'SECTIONLAB,Length,From,To,Coverage (total),Coverage (valid)\nA,10,0,10,0.2,0.2\n'
    response = client.post('/vaisala/upload/raw?network_key=stroud', headers=headers['manager'],
                           files={'file': ('qc.csv', raw, 'text/csv')})
    assert response.status_code == 201, response.text
    survey = response.json()['survey_id']
    for scale in ('section', '100m', '10m'):
        response = client.get(f'/vaisala/surveys/{survey}/sections/all?merge_scale={scale}', headers=headers['viewer'])
        assert response.status_code == 200, response.text
        assert response.json()[0]['qc_completeness_pct'] == 20
        assert response.json()[0]['qc_reliability_pct'] == 100
    response = client.get(f'/vaisala/surveys/{survey}/export', headers=headers['manager'])
    assert response.status_code == 200
    frame = pd.read_csv(io.StringIO(response.text))
    assert frame['Survey Completeness (%)'].iloc[0] == 20
    assert frame['Reading Reliability (%)'].iloc[0] == 100


def test_aliases_and_mixed_missing_coverage_use_independent_weights():
    raw = b'SECTIONLAB,Length,total_coverage,valid_coverage\nA,10,0.5,\nA,30,1,0.5\n'
    result = parse_raw_csv(raw, 'stroud')
    section = result['sections'][0]
    assert section['qc_completeness_pct'] == 87.5
    assert section['qc_reliability_pct'] == pytest.approx(100 * 0.5 / 0.875)
    intervals = [SimpleNamespace(id=i, **row) for i, row in enumerate(result['intervals'])]
    grouped = _intervals_to_100m_sections(intervals, 1)[0]
    assert grouped['qc_completeness_pct'] == section['qc_completeness_pct']
    assert grouped['qc_reliability_pct'] == section['qc_reliability_pct']
