import csv
import io
from test_evidence_reporting import api
from test_vaisala_programme_api import survey
from services.vaisala_programme import ACTIONS


def test_condition_views_share_programme_actions_and_rule_diagnostics(api, survey):
    client, headers, _ = api
    base = f'/vaisala/surveys/{survey}'
    programme = client.get(base + '/programme', headers=headers['viewer']).json()
    rows = client.get(base + '/sections/all', headers=headers['viewer']).json()
    lookup = {item['section_ref']: item for item in programme['items']}
    for row in rows:
        item = lookup[row['section_ref']]
        assert row['recommended_action'] == ACTIONS[item['recommended_action']]
        assert row['treatment_assessment'] == item['treatment_assessment']
    stats = client.get(base + '/stats', headers=headers['viewer']).json()
    assert stats['action_counts'] == {ACTIONS[k]: v for k, v in programme['summary']['action_counts'].items()}
    assert len(stats['action_counts']) == 5
    assert stats['action_diagnostics'] == programme['summary']['action_diagnostics']
    assert stats['action_diagnostics']['reason_counts']['significant_observation'] == 0
    assert stats['action_diagnostics']['structural_group_extent']['min_pct'] == 1
    assert sum(stats['action_diagnostics']['reason_counts'].values()) == 5
    export = client.get(base + '/export', headers=headers['viewer'])
    exported = list(csv.DictReader(io.StringIO(export.text)))
    assert {r['Section']: r['Next action'] for r in exported} == {
        r['section_ref']: r['recommended_action'] for r in rows}


def test_authority_policy_used_by_both_condition_and_programme_views(api, survey):
    from models.vaisala import VaisalaSection
    client, headers, sessions = api
    with sessions() as db:
        section = db.query(VaisalaSection).filter_by(survey_id=survey, section_ref='P4').one()
        section.dressing_pct = 6
        section.defect_proportions = {**section.defect_proportions, 'Severe fretting': 6}
        section.priority_score = 1
        db.commit()
    base = f'/vaisala/surveys/{survey}'
    policy = client.post(base + '/programme/policies', headers=headers['admin'],
                        json={'version': 'surface10', 'surface_threshold_pct': 10})
    assert policy.status_code == 201, policy.text
    rows = client.get(base + '/sections/all', headers=headers['viewer']).json()
    row = next(r for r in rows if r['section_ref'] == 'P4')
    assert row['recommended_action'] == 'Monitor observed deterioration'
    assert row['treatment_assessment']['candidates'] == []
    assert row['priority_score'] == 1


def test_proportionate_actions_reconcile_across_live_views_exports_and_snapshot(api):
    from models.vaisala import VaisalaSection, VaisalaSurvey
    from test_vaisala_proportionate_actions import observed
    client, headers, sessions = api
    examples = [
        ('MINOR', {'Minor longitudinal cracking': .4}, {}, 'no_action_indicated'),
        ('WATCH', {'Alligator cracking': 2}, {}, 'monitor'),
        ('APPRAISE', {'Moderate fretting': 6}, {}, 'treatment_appraisal'),
        ('ASSESS', {'Alligator cracking': 30}, {'rag_band': 'Amber'}, 'engineer_assessment'),
        ('VALIDATE', {'Minor longitudinal cracking': .2}, {'defect_evidence_complete': None}, 'evidence_validation'),
    ]
    with sessions() as db:
        survey = VaisalaSurvey(authority_id=1, source_filename='actions-v2.csv', source_format='csv', network_key='test')
        db.add(survey)
        db.flush()
        survey_id = survey.id
        for ref, defects, changes, _ in examples:
            data = observed(defects, **changes)
            for key in ('id', 'assessment_scope', 'section_ref'):
                data.pop(key)
            db.add(VaisalaSection(survey_id=survey_id, authority_id=1, section_ref=ref, **data))
        db.commit()
    base = f'/vaisala/surveys/{survey_id}'
    programme = client.get(base + '/programme', headers=headers['viewer']).json()
    assert programme['model_version'] == 'vaisala-programme-v3.1'
    assert programme['summary']['action_counts'] == {action: 1 for action in ACTIONS}
    lookup = {r['section_ref']: r for r in programme['items']}
    for ref, _, _, action in examples:
        assert lookup[ref]['recommended_action'] == action
    assert lookup['WATCH']['queue_rank'] is None
    assert lookup['WATCH']['prerequisite_tasks'] == ['record_monitoring_review']
    assert lookup['MINOR']['treatment_candidates'] == []
    condition = client.get(base + '/sections/all', headers=headers['viewer']).json()
    assert {r['section_ref']: r['recommended_action'] for r in condition} == {
        ref: ACTIONS[action] for ref, _, _, action in examples}
    stats = client.get(base + '/stats', headers=headers['viewer']).json()
    assert stats['action_diagnostics'] == programme['summary']['action_diagnostics']
    exported = list(csv.DictReader(io.StringIO(client.get(base + '/programme/export?format=csv', headers=headers['viewer']).text)))
    assert {r['section_ref']: r['recommended_action'] for r in exported} == {
        ref: action for ref, _, _, action in examples}
    snapshot = client.post(base + '/programmes', headers=headers['manager'], json={'idempotency_key': 'v2'}).json()
    custom = client.post(base + '/programme/policies', headers=headers['admin'],
                         json={'version': 'minor-stricter', 'acceptable_minor_extent_pct': .1})
    assert custom.status_code == 201
    revised = client.get(base + '/programme', headers=headers['viewer']).json()
    assert next(r for r in revised['items'] if r['section_ref'] == 'MINOR')['recommended_action'] == 'monitor'
    frozen = client.get(base + f"/programmes/{snapshot['id']}", headers=headers['viewer']).json()
    assert frozen['items'] == snapshot['items']
    assert client.get('/health').json()['vaisala_action_model'] == 'vaisala-programme-v3.1'


def test_old_policy_is_available_without_enabling_monitoring(api, survey):
    from models.vaisala_programme import VaisalaProgrammePolicy
    from services.vaisala_programme import LEGACY_DEFAULT_POLICY
    client, headers, sessions = api
    with sessions() as db:
        db.add(VaisalaProgrammePolicy(authority_id=1, version='existing-custom',
                                     policy={**LEGACY_DEFAULT_POLICY, 'version': 'existing-custom'}, created_by=1))
        db.commit()
    base = f'/vaisala/surveys/{survey}/programme'
    active = client.get(base, headers=headers['viewer']).json()
    assert active['policy']['routing_rules'] == 'legacy_v1'
    assert active['policy']['automatic_monitoring_enabled'] is False
    pinned = client.get(base, headers=headers['viewer'], params={'policy_version': LEGACY_DEFAULT_POLICY['version']})
    assert pinned.status_code == 200
    for version in ('vaisala-programme-default-v1', 'vaisala-programme-default-v2'):
        assert client.post(base + '/policies', headers=headers['admin'], json={'version': version}).status_code == 409
