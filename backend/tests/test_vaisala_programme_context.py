import json
from test_evidence_reporting import api, ai_requests
from models.vaisala import VaisalaSurvey, VaisalaSection, VaisalaInterval
from services.vaisala_scoring import RAG_VALIDATED_WEIGHTS


def test_programme_retains_unknown_urban_classification_and_missing_scores(api):
    client, headers, sessions = api
    with sessions() as db:
        survey = VaisalaSurvey(authority_id=1, source_filename='mixed.csv', source_format='csv', network_key='test')
        db.add(survey); db.flush()
        survey_id = survey.id
        for name, area in [('U', 'U'), ('R', 'R'), ('UNKNOWN', None)]:
            db.add(VaisalaSection(survey_id=survey.id, authority_id=1, section_ref=name, urban_rural=area,
                                 length_m=20, priority_score=0, rag_band='Green'))
            for start in [0, 10]:
                db.add(VaisalaInterval(survey_id=survey.id, authority_id=1, section_ref=name, urban_rural=area,
                    length_m=10, from_m=start, to_m=start+10, interval_score=None if name == 'UNKNOWN' else 1,
                    structural=.1, alligator=0, localised=0, dressing=0, micro=0, edge=0,
                    extras_json=json.dumps({'Coverage (total)': 1, 'Coverage (valid)': 1})))
        db.commit()
    response = client.get(f'/vaisala/surveys/{survey_id}/programme?merge_scale=10m', headers=headers['manager'])
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['summary']['total_items'] == 5
    assert payload['summary']['known_length_m'] == 60
    unknown = [r for r in payload['items'] if r['section_ref'] == 'UNKNOWN']
    assert len(unknown) == 2
    assert all(r['priority_score'] is None and r['queue_rank'] is None for r in unknown)
    urban = [r for r in payload['items'] if r['section_ref'] == 'U']
    assert len(urban) == 1 and urban[0]['assessment_scope'] == 'section'
    from services.vaisala_programme import ACTIONS
    for scale in ('10m', '100m'):
        scoped = client.get(f'/vaisala/surveys/{survey_id}/programme?merge_scale={scale}', headers=headers['manager']).json()
        listed = client.get(f'/vaisala/surveys/{survey_id}/sections/all?merge_scale={scale}', headers=headers['manager']).json()
        stats = client.get(f'/vaisala/surveys/{survey_id}/stats?merge_scale={scale}', headers=headers['manager']).json()
        assert {r['programme_item_key']: r['recommended_action'] for r in listed} == {
            r['item_key']: ACTIONS[r['recommended_action']] for r in scoped['items']}
        assert stats['action_counts'] == {ACTIONS[k]: v for k, v in scoped['summary']['action_counts'].items()}


def test_section_ai_uses_programme_zero_action_and_explicit_scope(api, ai_requests):
    client, headers, sessions = api
    with sessions() as db:
        survey = VaisalaSurvey(authority_id=1, source_filename='clean.csv', source_format='csv', network_key='test')
        db.add(survey); db.flush()
        section = VaisalaSection(survey_id=survey.id, authority_id=1, section_ref='CLEAN', net_reference='LINK-1', length_m=100,
            priority_score=0, rag_band='Green', structural_pct=0, alligator_pct=0, localised_pct=0,
            dressing_pct=0, micro_pct=0, edge_pct=0, defect_evidence_complete=True,
            defect_proportions={k: 0 for k in RAG_VALIDATED_WEIGHTS}, qc_completeness_pct=100, qc_reliability_pct=100)
        db.add(section); db.commit(); section_id = section.id; survey_id = survey.id
    response = client.post(f'/analysis/vaisala/{section_id}', headers=headers['manager'])
    assert response.status_code == 200
    context = ai_requests[-1]['messages'][0]['content']
    assert 'no_action_indicated' in context
    assert 'whole-section preview, not a saved client decision' in context
    assert 'Do not invent a queue rank' in context
    preview = client.get(f'/vaisala/surveys/{survey_id}/programme', headers=headers['manager']).json()
    assert preview['items'][0]['item_key'] in context


def test_interval_only_survey_recovers_section_coverage_and_urban_scope(api):
    client, headers, sessions = api
    with sessions() as db:
        survey = VaisalaSurvey(authority_id=1, source_filename='intervals.csv', source_format='csv', network_key='test')
        db.add(survey); db.flush(); survey_id = survey.id
        for area in ('U', 'R'):
            for start in (0, 10):
                db.add(VaisalaInterval(survey_id=survey_id, authority_id=1, section_ref=area, urban_rural=area,
                    length_m=10, from_m=start, to_m=start+10, interval_score=2,
                    structural=.1, alligator=0, localised=0, dressing=0, micro=0, edge=0))
        db.commit()
    default = client.get(f'/vaisala/surveys/{survey_id}/programme', headers=headers['manager'])
    assert default.status_code == 200, default.text
    assert default.json()['summary']['total_items'] == 2
    assert default.json()['summary']['known_length_m'] == 40
    listed = client.get(f'/vaisala/surveys/{survey_id}/sections/all', headers=headers['manager']).json()
    assert {r['programme_item_key'] for r in listed} == {r['item_key'] for r in default.json()['items']}
    assert all(item['parent_section_id'] is None for item in default.json()['items'])
    scaled = client.get(f'/vaisala/surveys/{survey_id}/programme?merge_scale=10m', headers=headers['manager']).json()
    assert len(scaled['items']) == 3
    assert len([item for item in scaled['items'] if item['assessment_scope'] == 'section' and item['section_ref'] == 'U']) == 1
    assert scaled['summary']['known_length_m'] == 40
