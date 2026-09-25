from test_vaisala_proportionate_actions import observed
from services.vaisala_programme import programme_item, DEFAULT_POLICY, LEGACY_DEFAULT_POLICY
import pytest


@pytest.mark.parametrize('policy', [DEFAULT_POLICY, LEGACY_DEFAULT_POLICY])
def test_small_local_subsidence_does_not_escalate_green_section(policy):
    row = observed({'Subsidence': .0317, 'Minor longitudinal cracking': .0231,
                    'Moderate longitudinal cracking': .0688, 'Minor transverse cracking': .0494,
                    'Moderate fretting': .0615})
    item = programme_item(row, survey_id=1, policy=policy)
    assert item['recommended_action'] == 'no_action_indicated'
    assert item['treatment_assessment']['local_defect_flags'][0]['defect'] == 'Subsidence'
    assert item['priority_score'] == row['priority_score']
    assert item['treatment_candidates'] == []


@pytest.mark.parametrize('detail', [{'Severe pothole': .1}, {'Wheel track cracking': 5},
                                   {'Minor transverse cracking': 2}])
def test_green_section_never_engineer_assessment(detail):
    item = programme_item(observed(detail), survey_id=1, policy=DEFAULT_POLICY)
    assert item['recommended_action'] != 'engineer_assessment'


def test_incomplete_green_keeps_local_observation_without_clearance():
    item = programme_item(observed({'Severe pothole': .1}, defect_evidence_complete=False),
                          survey_id=1, policy=DEFAULT_POLICY)
    assert item['recommended_action'] == 'evidence_validation'
    assert item['treatment_assessment']['local_defect_flags']
    assert item['treatment_candidates'] == []


def test_validation_explains_known_defects_and_specific_qc_gap():
    row = observed({'Severe transverse cracking': 54.8658}, priority_score=9.2493,
                   rag_band='Red', defect_evidence_complete=False,
                   qc_completeness_pct=100, qc_reliability_pct=79.905206)
    item = programme_item(row, survey_id=1, policy=DEFAULT_POLICY)
    assert item['recommended_action'] == 'evidence_validation'
    assert item['priority_score'] == 9.2493
    assert 'Defects are recorded' in item['brief']
    assert '79.9%, below the policy requirement of 85%' in item['brief']
    assert 'complete valid defect readings are not established' in item['brief']
    assert item['treatment_assessment']['candidate_status_text'] == 'Treatment selection pending evidence validation'


def test_unknown_readings_do_not_claim_confirmed_defects():
    item = programme_item(observed(defect_evidence_complete=False), survey_id=1, policy=DEFAULT_POLICY)
    assert 'Defects are recorded' not in item['brief']
    assert 'insufficient to establish condition' in item['brief']


def test_chainage_subsections_and_full_defect_evidence_survive_import():
    import io
    import json
    import pandas as pd
    from services.vaisala_scoring import parse_raw_xlsx, RAG_VALIDATED_WEIGHTS
    from services.vaisala_section_appraisal import attach_local_locations
    rows = [dict(NSGNO='123', WSCCNET=net, Length=10,
                 **{'From meters': 0, 'To meters': 10},
                 **{k: (.002 if k == 'Subsidence' else 0) for k in RAG_VALIDATED_WEIGHTS})
            for net in ['123/1', '123/2']]
    stream = io.BytesIO()
    pd.DataFrame(rows).to_excel(stream, index=False)
    parsed = parse_raw_xlsx(stream.getvalue(), 'wscc')
    assert len(parsed['intervals']) == 2
    assert parsed['dup_groups'] == 0
    assert all(iv['from_m'] == 0 and iv['to_m'] == 10 for iv in parsed['intervals'])
    assert json.loads(parsed['intervals'][0]['extras_json'])['defect_proportions']['Subsidence'] == .2
    attach_local_locations(parsed['sections'], parsed['intervals'])
    flag = parsed['sections'][0]['local_defect_flags'][0]
    assert {v['net_reference'] for v in flag['locations']} == {'123/1', '123/2'}
