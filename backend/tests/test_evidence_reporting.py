from types import SimpleNamespace

import pytest
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from test_admin import api
from models.asset import Asset, ScannerRawRecord, ScrimRecord
from models.vaisala import VaisalaSurvey, VaisalaSection
from routers import analysis
from services import llm


@compiles(JSONB, 'sqlite')
def _sqlite_jsonb(element, compiler, **kwargs):
    # These API tests exercise JSON payloads, not PostgreSQL JSONB operators.
    return 'JSON'


@pytest.fixture
def ai_requests(monkeypatch):
    requests = []
    def create(**kwargs):
        requests.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(text='Assessment')],
                               usage=SimpleNamespace(input_tokens=1, output_tokens=1))
    monkeypatch.setattr(llm, '_get_client', lambda: SimpleNamespace(messages=SimpleNamespace(create=create)))
    analysis._narrative_cache.clear()
    yield requests
    analysis._narrative_cache.clear()


@pytest.mark.parametrize('qc', [95.3, None])
def test_vaisala_ai_receives_evidence_units_and_limits(api, ai_requests, qc):
    client, headers, sessions = api
    with sessions() as db:
        survey = VaisalaSurvey(authority_id=1, source_filename='evidence.csv',
                               source_format='csv', network_key='test')
        db.add(survey); db.flush()
        section = VaisalaSection(survey_id=survey.id, authority_id=1, section_ref='EVIDENCE',
            length_m=100, priority_score=4.5, rag_band='Red', treatment='Resurfacing',
            structural_pct=20, qc_completeness_pct=qc, qc_reliability_pct=qc,
            defect_proportions={'Wheel track cracking': 20})
        db.add(section); db.commit()
        section_id = section.id
        survey_id = survey.id
    assert client.post(f'/analysis/vaisala/{section_id}', headers=headers['manager']).status_code == 200
    request = ai_requests[-1]
    context = request['messages'][0]['content']
    assert 'Indicative treatment candidate: Resurfacing' in context
    assert '% of weighted score' not in context
    assert 'Wheel track cracking=20.0%' in context
    if qc is not None:
        assert 'Completeness=95.3%' in context
        assert 'Reliability=95.3%' in context
        assert '9530' not in context
    else:
        assert 'QC signals: unknown' in context
    assert 'structural capacity' in request['system'][0]['text']
    assert 'hypotheses' in request['system'][0]['text']
    # Evidence remains authority-scoped.
    with sessions() as db:
        db.get(VaisalaSurvey, survey_id).authority_id = 2
        db.commit()
    assert client.post(f'/analysis/vaisala/{section_id}', headers=headers['manager']).status_code == 404


def test_asset_ai_percentages_and_scrim_investigation(api, ai_requests):
    client, headers, sessions = api
    with sessions() as db:
        asset = Asset(authority_id=1, nsg_ref='REPORTING', road_name='Example Road')
        db.add(asset); db.flush()
        db.add(ScannerRawRecord(asset_id=asset.id, survey_year=2026, avg_ci=36.9,
                               rci_band='Red', red_pct=4.35))
        db.add(ScrimRecord(asset_id=asset.id, survey_year=2026, safety_flagged=True,
                           pct_below_il=5.5, mean_sfc=0.3))
        db.commit()
    response = client.post('/analysis/asset/REPORTING', headers=headers['manager'])
    assert response.status_code == 200
    context = ai_requests[-1]['messages'][0]['content']
    assert 'red_pct=4.35%' in context
    assert 'pct_below_il=5.50%' in context
    row = client.get('/assets/', headers=headers['manager']).json()['assets'][0]
    assert 'skid resistance investigation' in row['treatment_recommendation']
    assert 'skid resistance treatment' not in row['treatment_recommendation']
    assert row['urgency'] != 'Immediate'
    assert row['scrim_score'] == 25.5
    assert row['composite_score'] == 74.2


def test_shared_prompt_has_no_authority_findings_or_unverified_cost_rules():
    prompt = llm._build_system_prompt()
    assert 'WSCC' not in prompt
    assert 'West Sussex' not in prompt
    assert '5–10' not in prompt
    assert 'CI <35 / RCI Red' not in prompt
    assert 'hypotheses' in prompt
    assert 'percentile' in prompt.lower()
