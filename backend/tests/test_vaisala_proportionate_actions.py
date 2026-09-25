"""Behavioural boundaries for the severity/extent action model; no score changes."""
import copy

import pytest

from services.vaisala_programme import DEFAULT_POLICY, programme_item, validate_policy
from services.vaisala_scoring import RAG_VALIDATED_WEIGHTS


def observed(defects=None, **changes):
    from services.vaisala_treatments import GROUP_DEFECTS
    detail = {key: 0 for key in RAG_VALIDATED_WEIGHTS}
    detail.update(defects or {})
    row = dict(id=1, section_ref='example', length_m=100, assessment_scope='section',
               defect_proportions=detail, defect_evidence_complete=True,
               qc_completeness_pct=95, qc_reliability_pct=95,
               priority_score=sum(detail[k] * w for k, w in RAG_VALIDATED_WEIGHTS.items()) / sum(RAG_VALIDATED_WEIGHTS.values()),
               rag_band='Green', **{group: max(detail[k] for k in keys) for group, keys in GROUP_DEFECTS.items()})
    row.update(changes)
    return row


def assess(row, **policy):
    before = copy.deepcopy(row)
    result = programme_item(row, survey_id=1, policy={**DEFAULT_POLICY, **policy})
    assert row == before
    assert result['priority_score'] == row['priority_score']
    assert result['rag_band'] == row['rag_band']
    return result


@pytest.mark.parametrize('defects,action', [
    ({'Minor longitudinal cracking': .4, 'Moderate fretting': .4}, 'no_action_indicated'),
    ({'Minor longitudinal cracking': 1}, 'monitor'),
    ({'Moderate longitudinal cracking': .2}, 'monitor'),
    ({'Alligator cracking': .2}, 'monitor'),
    ({'Wheel track cracking': 4.99}, 'monitor'),
    ({'Wheel track cracking': 5}, 'engineer_assessment'),
    ({'Alligator cracking': 5}, 'engineer_assessment'),
    ({'Left edge deterioration': .2}, 'monitor'),
    ({'Left edge deterioration': 5}, 'engineer_assessment'),
    ({'Moderate fretting': 5}, 'treatment_appraisal'),
    ({'Minor pothole': 5}, 'treatment_appraisal'),
])
def test_type_and_extent_routes(defects, action):
    result = assess(observed(defects))
    assert result['recommended_action'] == action
    if action in ('monitor', 'no_action_indicated'):
        assert result['treatment_candidates'] == []
    if action == 'monitor':
        assert 'review' in result['brief'].lower()


@pytest.mark.parametrize('defect', ['Severe pothole', 'Subsidence', 'Severe longitudinal cracking',
                                  'Severe transverse cracking', 'Moderate pothole', 'Binder bleeding'])
def test_local_significant_observation_cannot_be_diluted(defect):
    row = observed({'Minor longitudinal cracking': .5, defect: .0001})
    assert assess(row)['recommended_action'] == 'engineer_assessment'


@pytest.mark.parametrize('change', [
    {'defect_evidence_complete': None}, {'defect_evidence_complete': False},
    {'qc_reliability_pct': 84.99}, {'qc_completeness_pct': None},
    {'defect_proportions': None}, {'priority_score': None},
])
def test_missing_evidence_cannot_be_accepted_or_monitored(change):
    assert assess(observed({'Minor longitudinal cracking': .2}, **change))['recommended_action'] == 'evidence_validation'


def test_acceptable_limit_is_combined_not_per_defect_and_configurable():
    row = observed({'Minor longitudinal cracking': .6, 'Minor transverse cracking': .6})
    assert assess(row)['recommended_action'] == 'monitor'
    assert assess(row, acceptable_minor_extent_pct=2)['recommended_action'] == 'no_action_indicated'
    assert assess(observed({'Minor longitudinal cracking': .1}), acceptable_minor_extent_pct=0)['recommended_action'] == 'monitor'


def test_unclassified_label_alone_does_not_clear_risk():
    assert assess(observed({'Severe pothole': .1}, road_class='U'))['recommended_action'] == 'engineer_assessment'


def test_unknown_structural_type_and_positive_driver_still_require_assessment():
    assert assess(observed(structural_pct=.1, defect_proportions=None))['recommended_action'] == 'engineer_assessment'
    assert assess(observed(primary_defect='Severe pothole', primary_defect_contribution=.01))['recommended_action'] == 'engineer_assessment'


def test_low_section_mean_cannot_clear_known_local_high_score():
    assert assess(observed({'Minor longitudinal cracking': .1}, worst_interval_score=4))['recommended_action'] == 'engineer_assessment'


def test_monitoring_opt_out_and_invalid_policy():
    assert assess(observed({'Moderate fretting': 2}), automatic_monitoring_enabled=False)['recommended_action'] == 'engineer_assessment'
    for change in ({'acceptable_minor_extent_pct': float('nan')}, {'structural_assessment_pct': -1},
                   {'automatic_monitoring_enabled': 'yes'}, {'acceptable_minor_extent_pct': 6}):
        with pytest.raises(ValueError):
            validate_policy({**DEFAULT_POLICY, **change})


@pytest.mark.parametrize('additional', ['Wheel track cracking', 'Left edge deterioration'])
def test_mixed_deterioration_cannot_be_downgraded_to_monitor(additional):
    result = assess(observed({additional: .2, 'Severe fretting': 20}))
    assert result['recommended_action'] == 'engineer_assessment'
    assert result['reason_codes'] == ['mixed_deterioration']


@pytest.mark.parametrize('group', ['micro_pct', 'localised_pct'])
def test_group_only_appraisal_does_not_hide_unknown_severity(group):
    result = assess(observed(defect_proportions=None, **{group: 5}))
    assert result['recommended_action'] == 'evidence_validation'


def test_conflicting_group_extent_cannot_establish_minor_condition():
    result = assess(observed({'Minor longitudinal cracking': .1}, micro_pct=4))
    assert result['recommended_action'] == 'engineer_assessment'
    assert result['evidence_status'] == 'conflicting'


def test_aggregation_rounding_does_not_create_false_conflict():
    assert assess(observed({'Minor longitudinal cracking': .1049}, micro_pct=.10))['recommended_action'] == 'no_action_indicated'


def test_legacy_policy_keeps_original_routing():
    from services.vaisala_programme import LEGACY_DEFAULT_POLICY
    result = programme_item(observed({'Minor longitudinal cracking': .2}), survey_id=1, policy=LEGACY_DEFAULT_POLICY)
    assert result['recommended_action'] == 'engineer_assessment'
    assert result['policy_version'] == 'vaisala-programme-default-v1'


@pytest.mark.parametrize('invalid', [-1, 101, float('nan'), float('inf'), True, 'unreadable'])
@pytest.mark.parametrize('minor', [0, .2])
def test_invalid_individual_readings_never_establish_lower_action(invalid, minor):
    row = observed({'Minor longitudinal cracking': minor})
    row['defect_proportions']['Subsidence'] = invalid
    # Bypass the non-mutation equality helper: NaN is not equal to itself.
    result = programme_item(row, survey_id=1, policy=DEFAULT_POLICY)
    assert result['recommended_action'] == 'evidence_validation'


def test_combined_minor_boundary_is_stable_for_decimal_values():
    row = observed({'Minor longitudinal cracking': .1, 'Minor transverse cracking': .2, 'Moderate fretting': .7})
    assert assess(row)['recommended_action'] == 'monitor'
