import copy
import pytest
from services.vaisala_programme import DEFAULT_POLICY, build_programme, programme_item
from services.vaisala_scoring import RAG_VALIDATED_WEIGHTS
from services.vaisala_scoring import EDGE_KEYS


def row(id=1, **changes):
    value = dict(id=id, section_ref=str(id), assessment_scope='section', length_m=100,
                 priority_score=0, rag_band='Green', structural_pct=0, alligator_pct=0,
                 localised_pct=0, dressing_pct=0, micro_pct=0, edge_pct=0,
                 defect_evidence_complete=True, defect_proportions={k: 0 for k in RAG_VALIDATED_WEIGHTS},
                 qc_completeness_pct=95, qc_reliability_pct=95)
    value.update(changes)
    return value


@pytest.mark.parametrize('changes,expected', [
    ({}, 'no_action_indicated'),
    ({'structural_pct': .1}, 'engineer_assessment'),
    ({'edge_pct': .1, 'defect_evidence_complete': None}, 'engineer_assessment'),
    ({'dressing_pct': 5, 'priority_score': 1}, 'treatment_appraisal'),
    ({'localised_pct': .1}, 'engineer_assessment'),
    ({'defect_evidence_complete': None}, 'evidence_validation'),
    ({'qc_reliability_pct': 84.9}, 'evidence_validation'),
    ({'priority_score': 2, 'rag_band': 'Amber'}, 'engineer_assessment'),
    ({'priority_score': None}, 'evidence_validation'),
    ({'structural_pct': None, 'observed_defect_groups': ['structural_pct']}, 'engineer_assessment'),
])
def test_routing(changes, expected):
    result = programme_item(row(**changes), survey_id=1, policy=DEFAULT_POLICY)
    assert result['recommended_action'] == expected
    assert result['brief'] and result['next_question']


def test_partial_evidence_preserved():
    result = programme_item(row(structural_pct=None, observed_defect_groups=['structural_pct']),
                            survey_id=1, policy=DEFAULT_POLICY)
    assert 'validate_evidence' in result['prerequisite_tasks']
    assert not any(c['name'] == 'Surface dressing' for c in result['treatment_assessment']['candidates'])


@pytest.mark.parametrize('use_driver', [False, True])
def test_individual_edge_evidence_survives_missing_aggregate(use_driver):
    defect = next(iter(EDGE_KEYS))
    changes = {'primary_defect': defect, 'primary_defect_contribution': .1} if use_driver else {'defect_proportions': {defect: 2}}
    result = programme_item(row(edge_pct=None, **changes), survey_id=1, policy=DEFAULT_POLICY)
    assert result['recommended_action'] == 'engineer_assessment'
    assert result['reason_codes'] == ['edge_observed']
    assert 'validate_evidence' in result['prerequisite_tasks']
    assert defect in ' '.join(result['treatment_assessment']['evidence'])


def test_rank_ties_scales_nulls_and_immutability():
    rows = [row(1, dressing_pct=5, priority_score=4), row(2, dressing_pct=5, priority_score=4),
            row(3, dressing_pct=5, priority_score=2), row(4, dressing_pct=5, priority_score=None),
            row(5, dressing_pct=5, priority_score=8, assessment_scope='10m', source_interval_ids=[5])]
    before = copy.deepcopy(rows)
    result = build_programme(rows, survey_id=1, policy=DEFAULT_POLICY)
    indexed = {r['id']: r for r in result['items']}
    assert [indexed[i]['queue_rank'] for i in range(1, 6)] == [1, 1, 3, None, 1]
    assert indexed[1]['queue_size'] == 3
    assert rows == before
    reverse = build_programme(list(reversed(rows)), survey_id=1, policy=DEFAULT_POLICY)
    assert result == reverse


def test_overlaps_and_missing_chainage_are_not_invented():
    rows = [row(i, section_ref='S', assessment_scope='10m', source_interval_ids=[i],
                source_extents=extents) for i, extents in enumerate([
                    [{'from_m': 0, 'to_m': 10}], [{'from_m': 5, 'to_m': 15}],
                    [{'from_m': None, 'to_m': None}]], 1)]
    result = build_programme(rows, survey_id=1, policy=DEFAULT_POLICY)
    assert result['summary']['known_length_m'] == 15
    assert result['summary']['unresolved_extents'] == 1
    assert sum(result['summary']['action_counts'].values()) == 3


def test_policy_affects_screening_not_scores():
    custom = {**DEFAULT_POLICY, 'version': 'custom', 'surface_threshold_pct': 10}
    source = row(dressing_pct=6, priority_score=1)
    result = programme_item(source, survey_id=1, policy=custom)
    assert result['recommended_action'] == 'engineer_assessment'
    assert result['priority_score'] == 1
    with pytest.raises(ValueError):
        build_programme([], survey_id=1, policy={**DEFAULT_POLICY, 'automatic_monitoring_enabled': True})


def test_custom_qc_policy_does_not_mislabel_existing_high_band():
    policy = {**DEFAULT_POLICY, 'qc_adequacy_pct': 98}
    result = programme_item(row(), survey_id=1, policy=policy)
    assert result['recommended_action'] == 'evidence_validation'
    gaps = ' '.join(result['treatment_assessment']['evidence_gaps'])
    assert 'policy threshold (98%)' in gaps
    assert 'below the existing High band' not in gaps


def test_zero_policy_triggers_still_require_positive_observations():
    policy = {**DEFAULT_POLICY, 'localised_threshold_pct': 0, 'surface_threshold_pct': 0}
    result = programme_item(row(), survey_id=1, policy=policy)
    assert result['recommended_action'] == 'no_action_indicated'
    assert result['treatment_candidates'] == []
