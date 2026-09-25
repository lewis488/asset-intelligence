import io
import json
import zipfile

import pandas as pd
import pytest
from test_evidence_reporting import api, ai_requests  # also adapts JSONB for SQLite tests
from models.vaisala import VaisalaSurvey, VaisalaSection, VaisalaInterval, VaisalaNetworkGeometry, VaisalaNetworkFeature
from services.vaisala_treatments import assess_treatments, add_priority_percentiles
from services.vaisala_scoring import RAG_VALIDATED_WEIGHTS


def row(**changes):
    return dict(structural_pct=0, alligator_pct=0, localised_pct=0,
                dressing_pct=0, micro_pct=0, edge_pct=0,
                defect_proportions={key: 0 for key in RAG_VALIDATED_WEIGHTS},
                defect_evidence_complete=True,
                qc_completeness_pct=95, qc_reliability_pct=95, **changes)


def evidence(**changes):
    result = row()
    result.update(changes)
    return result


def names(result):
    return {candidate['name'] for candidate in result['candidates']}


@pytest.mark.parametrize('field,value', [('structural_pct', 20), ('alligator_pct', 15), ('structural_pct', 0.1)])
def test_structural_indications_trigger_investigation_not_resurfacing(field, value):
    assessment = assess_treatments(evidence(**{field: value, 'dressing_pct': 25}))
    assert assessment['action'] == 'Investigate'
    assert 'Resurfacing' not in names(assessment)
    assert 'Surface dressing' not in names(assessment)
    assert assessment['candidates']
    assert all(c['prerequisites'] and c['cautions'] for c in assessment['candidates'])
    assert any('structural' in gap.lower() for gap in assessment['evidence_gaps'])


def test_surface_groups_produce_alternatives_not_dominance_choice():
    assessment = assess_treatments(evidence(dressing_pct=5, micro_pct=10))
    assert assessment['action'] == 'Appraise maintenance options'
    assert {'Surface dressing', 'Micro-surfacing', 'Thin surfacing'} <= names(assessment)
    assert all('conditional' == c['status'] for c in assessment['candidates'])


def test_edge_and_localised_candidates_have_different_checks():
    assessment = assess_treatments(evidence(localised_pct=5, edge_pct=8))
    assert {'Localised patch repair', 'Edge repair / haunching'} <= names(assessment)
    assert 'drainage' in json.dumps(assessment).lower()
    assert 'recurrence' in json.dumps(assessment).lower()


def test_unknown_and_low_qc_are_not_monitor():
    assert assess_treatments({})['action'] == 'Inspect'
    assert assess_treatments(evidence(qc_completeness_pct=None))['action'] == 'Inspect'
    assert assess_treatments(evidence(qc_reliability_pct=20))['action'] == 'Inspect'
    assert assess_treatments(evidence())['action'] == 'Monitor'
    assert assess_treatments(evidence(localised_pct=0.1))['action'] == 'Inspect'
    assert assess_treatments(evidence(priority_score=4.5, rag_band='Red'))['action'] == 'Inspect'
    assert assess_treatments(evidence(defect_proportions={'Minor pothole': 0}, defect_evidence_complete=None))['action'] == 'Inspect'
    assert assess_treatments(evidence(defect_proportions=None, defect_evidence_complete=None))['action'] == 'Inspect'
    assert assess_treatments(evidence(defect_evidence_complete=None))['action'] == 'Inspect'
    assert assess_treatments(evidence(defect_proportions={'Severe pothole': 1}))['action'] == 'Investigate'
    assert assess_treatments(evidence(primary_defect='Subsidence', primary_defect_contribution=0.5))['action'] == 'Investigate'


def test_partial_structural_observations_survive_missing_aggregate():
    assessment = assess_treatments(evidence(structural_pct=None, dressing_pct=10,
        observed_defect_groups=['structural_pct']))
    assert assessment['action'] == 'Investigate'
    assert 'Surface dressing' not in names(assessment)


def test_ingestion_records_valid_readings_without_changing_condition_scores():
    from services.vaisala_scoring import parse_raw_csv
    fields = {'SECTIONLAB': ['VALID', 'BLANK'], 'Length': [10, 10],
              **{key: [0, 0] for key in RAG_VALIDATED_WEIGHTS}}
    fields['Wheel track cracking'][1] = None
    result = parse_raw_csv(pd.DataFrame(fields).to_csv(index=False).encode(), 'stroud')
    by_ref = {s['section_ref']: s for s in result['sections']}
    assert by_ref['VALID']['defect_evidence_complete'] is True
    assert by_ref['BLANK']['defect_evidence_complete'] is False
    assert {s['priority_score'] for s in result['sections']} == {0}
    assert [iv['defect_evidence_complete'] for iv in result['intervals']] == [True, False]


def test_invalid_or_conflicting_evidence_does_not_establish_suitability():
    assessment = assess_treatments(evidence(structural_pct=None, dressing_pct=10))
    assert assessment['action'] == 'Inspect'
    assert assessment['evidence_gaps']
    assert all(c['prerequisites'] for c in assessment['candidates'])
    assert assess_treatments(evidence(localised_pct=float('nan')))['action'] == 'Inspect'


def test_percentiles_are_tie_aware_scale_scoped_and_never_assign_treatments():
    rows = [dict(priority_score=s, assessment_scope=scope, treatment='unchanged')
            for s, scope in [(1, 'section'), (1, 'section'), (10, 'section'), (9, '10m'), (None, '10m')]]
    add_priority_percentiles(rows)
    assert [r['priority_percentile'] for r in rows] == [25, 25, 100, None, None]
    assert {r['treatment'] for r in rows} == {'unchanged'}


def test_existing_survey_candidates_match_api_modes_exports_and_ai(api, ai_requests):
    client, headers, sessions = api
    with sessions() as db:
        survey = VaisalaSurvey(authority_id=1, source_filename='legacy.csv', source_format='csv', network_key='test')
        db.add(survey); db.flush()
        survey_id = survey.id
        section = VaisalaSection(survey_id=survey_id, authority_id=1, section_ref='CANDIDATE',
            length_m=100, priority_score=4.5, rag_band='Red', treatment='Resurfacing', **evidence(structural_pct=20))
        db.add(section); db.commit()
        section_id = section.id
    base = f'/vaisala/surveys/{survey_id}'
    normal = client.get(base + '/sections', headers=headers['manager']).json()['sections'][0]
    ranked = client.get(base + '/sections?treatment_mode=percentile', headers=headers['manager']).json()['sections'][0]
    assert normal['treatment_assessment'] == ranked['treatment_assessment']
    assert normal['treatment'] != 'Resurfacing'
    assert normal['recommended_action'] == 'Validate evidence / further survey'
    assert normal['rag_band'] == 'Red' and normal['priority_score'] == 4.5
    export = client.get(base + '/export?treatment_mode=percentile', headers=headers['manager'])
    frame = pd.read_csv(io.StringIO(export.text))
    assert frame['Next action'].iloc[0] == 'Validate evidence / further survey'
    assert frame['Conditional candidates'].iloc[0] == 'No candidate selected'
    assert 'structural' in frame['Evidence gaps'].iloc[0].lower()
    assert 'Structural Defect Proportion (%)' in frame.columns
    workbook = client.get(base + '/export?format=xlsx', headers=headers['manager'])
    assert workbook.status_code == 200
    assert pd.read_excel(io.BytesIO(workbook.content))['Next action'].iloc[0] == 'Validate evidence / further survey'
    response = client.post(f'/analysis/vaisala/{section_id}', headers=headers['manager'])
    assert response.status_code == 200
    context = ai_requests[-1]['messages'][0]['content']
    assert 'Structured treatment assessment' in context
    assert 'Indicative treatment candidate: Resurfacing' not in context
    with sessions() as db:
        assert db.get(VaisalaSection, section_id).treatment == 'Resurfacing'  # no data rewrite
        geom = VaisalaNetworkGeometry(authority_id=1, source_filename='network.shp',
            section_field='Section', feature_count=1, is_active=True)
        db.add(geom); db.flush()
        db.add(VaisalaNetworkFeature(geometry_id=geom.id, section_key='CANDIDATE',
            geometry_geojson=json.dumps({'type': 'LineString', 'coordinates': [[-0.1, 51.0], [-0.1, 51.001]]})))
        db.commit()
    mapped = client.get(f'/vaisala/network-geometry/features?survey_id={survey_id}&treatment_mode=percentile', headers=headers['manager'])
    props = mapped.json()['features'][0]['properties']
    assert props['treatment_assessment'] == normal['treatment_assessment']
    assert props['programme_items'][0]['recommended_action'] == 'evidence_validation'
    assert props['programme_items'][0]['priority_score'] == 4.5
    shp = client.get(base + '/export?format=shp', headers=headers['manager'])
    assert shp.status_code == 200, shp.text[:500] if shp.status_code != 200 else ''
    with zipfile.ZipFile(io.BytesIO(shp.content)) as archive:
        assessment = json.loads(archive.read('treatment_assessments.json'))[0]
        assert assessment['treatment_assessment'] == normal['treatment_assessment']
        assert 'README.txt' in archive.namelist()
        programme = json.loads(archive.read('action_programme.json'))
        assert programme['items'][0]['item_key'] == props['programme_items'][0]['item_key']
        assert programme['summary']['total_items'] == 1


def test_scaled_views_keep_urban_scope_missing_evidence_and_parent_narrative(api):
    client, headers, sessions = api
    with sessions() as db:
        survey = VaisalaSurvey(authority_id=1, source_filename='scales.csv', source_format='csv', network_key='test')
        db.add(survey); db.flush()
        survey_id = survey.id
        for name, area in [('RURAL', 'R'), ('URBAN', 'U')]:
            section = VaisalaSection(survey_id=survey_id, authority_id=1, section_ref=name,
                urban_rural=area, length_m=20, priority_score=5, rag_band='Red', **evidence(structural_pct=20))
            db.add(section); db.flush()
            if name == 'RURAL':
                parent_id = section.id
            for start in (0, 10):
                db.add(VaisalaInterval(survey_id=survey_id, section_ref=name, urban_rural=area,
                    length_m=10, from_m=start, to_m=start+10, interval_score=5,
                    structural=0.2 if start == 0 else None, alligator=0, localised=0, dressing=0.1, micro=0, edge=None,
                    extras_json=json.dumps({'Coverage (total)': 1, 'Coverage (valid)': 1})))
        db.commit()
    for scale in ('10m', '100m'):
        response = client.get(f'/vaisala/surveys/{survey_id}/sections/all?merge_scale={scale}&treatment_mode=percentile', headers=headers['viewer'])
        assert response.status_code == 200, response.text
        rows = response.json()
        urban = [r for r in rows if r['section_ref'] == 'URBAN']
        rural = [r for r in rows if r['section_ref'] == 'RURAL']
        assert len(urban) == 1 and urban[0]['assessment_scope'] == 'section'
        assert urban[0]['priority_percentile'] is None  # never ranked against rural intervals
        assert len(rural) == (2 if scale == '10m' else 1)
        for r in rural:
            assert r['assessment_scope'] == scale
            assert r['narrative_section_id'] == parent_id
            assert r['recommended_action'] == 'Engineer assessment'  # known Red interval still needs assessment with limited evidence
            assert r['edge_pct'] is None
            assert 'Edge deterioration' in ' '.join(r['treatment_assessment']['evidence_gaps'])
            assert r['priority_score'] == 5


def test_evidence_migration_preserves_legacy_rows_and_is_reversible(monkeypatch):
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine, text
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / 'alembic/versions/019_vaisala_defect_evidence.py'
    spec = importlib.util.spec_from_file_location('evidence_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        for table in ('vaisala_sections', 'vaisala_intervals'):
            conn.execute(text(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, score FLOAT)'))
            conn.execute(text(f'INSERT INTO {table} VALUES (1, 4.5)'))
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(conn)))
        migration.upgrade()
        for table in ('vaisala_sections', 'vaisala_intervals'):
            assert conn.execute(text(f'SELECT score, defect_evidence_complete FROM {table}')).one() == (4.5, None)
        migration.downgrade()
        for table in ('vaisala_sections', 'vaisala_intervals'):
            assert conn.execute(text(f'SELECT * FROM {table}')).one() == (1, 4.5)
    engine.dispose()
