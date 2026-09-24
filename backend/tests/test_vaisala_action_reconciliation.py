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
    assert stats['action_diagnostics']['reason_counts']['structural_observed'] == 4
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
        section.priority_score = 1
        db.commit()
    base = f'/vaisala/surveys/{survey}'
    policy = client.post(base + '/programme/policies', headers=headers['admin'],
                        json={'version': 'surface10', 'surface_threshold_pct': 10})
    assert policy.status_code == 201, policy.text
    rows = client.get(base + '/sections/all', headers=headers['viewer']).json()
    row = next(r for r in rows if r['section_ref'] == 'P4')
    assert row['recommended_action'] == 'Engineer assessment'
    assert row['treatment_assessment']['candidates'] == []
    assert row['priority_score'] == 1
