"""Proportionate survey screening, separate from the frozen condition-score model.

Numerical limits are provisional authority policy, not CVI indices or national
intervention criteria. Only retained evidence can support a lower-action route.
"""
import math

from services.vaisala_scoring import RAG_VALIDATED_WEIGHTS, RAG_RED_THRESHOLD, RAG_AMBER_THRESHOLD
from services.vaisala_treatments import GROUP_DEFECTS, _number

MINOR_DEFECTS = frozenset({'Minor longitudinal cracking', 'Minor transverse cracking', 'Moderate fretting'})
SIGNIFICANT_DEFECTS = frozenset({'Subsidence', 'Severe pothole', 'Severe longitudinal cracking',
                               'Severe transverse cracking', 'Moderate pothole', 'Binder bleeding'})


def proportionate_action(source, flags, policy):
    """Return action/reason plus auditable observations; never infer missing zeros."""
    detail = source.get('defect_proportions') or {}
    readings = {k: _number(detail.get(k), 100) for k in RAG_VALIDATED_WEIGHTS}
    positives = {k for k, value in readings.items() if value is not None and value > 0}
    drivers = {source.get(f'{p}_defect') for p in ('primary', 'secondary')
               if (_number(source.get(f'{p}_defect_contribution')) or 0) > 0}
    observed = positives | drivers
    groups = {k: _number(source.get(k), 100) for k in GROUP_DEFECTS}
    all_types = all(v is not None for v in readings.values())
    minor_sum = math.fsum(readings[k] or 0 for k in MINOR_DEFECTS)
    evidence = dict(minor_extent_upper_bound_pct=minor_sum,
                    detailed_types_available=all_types,
                    significant_observations=sorted(observed & SIGNIFICANT_DEFECTS))

    def route(action, reason):
        return action, reason, evidence

    # Retained positive severe observations take precedence, even with poor QC.
    if observed & SIGNIFICANT_DEFECTS:
        return route('engineer_assessment', 'significant_observation')
    if (_number(source.get('worst_interval_score')) or 0) >= RAG_RED_THRESHOLD:
        return route('engineer_assessment', 'local_condition_concern')
    # A structural group contains mixed severities. A primary driver cannot
    # establish that every other structural defect was absent.
    structural_keys = GROUP_DEFECTS['structural_pct'] | GROUP_DEFECTS['alligator_pct']
    structural_known = all_types and bool(positives & structural_keys)
    if flags['structural_observed'] and not structural_known:
        return route('engineer_assessment', 'structural_observed')
    structural_extent = max(groups['structural_pct'] or 0, groups['alligator_pct'] or 0,
                            *(readings[k] or 0 for k in structural_keys))
    if flags['structural_observed'] and structural_extent >= policy['structural_assessment_pct']:
        return route('engineer_assessment', 'structural_extent')
    edge_extent = max(groups['edge_pct'] or 0, *(readings[k] or 0 for k in GROUP_DEFECTS['edge_pct']))
    if flags['edge_observed'] and (edge_extent >= policy['edge_assessment_pct'] or not all_types
                                   or not (positives & GROUP_DEFECTS['edge_pct'])):
        return route('engineer_assessment', 'edge_observed')
    if flags['evidence_conflict']:
        return route('engineer_assessment', 'evidence_conflict')
    if not flags['complete_readings'] or not flags['qc_adequate']:
        return route('evidence_validation', 'evidence_limited')
    if any(k in detail and v is None for k, v in readings.items()):
        return route('evidence_validation', 'evidence_limited')
    # Zero observations may still be established from complete valid groups.
    score = _number(source.get('priority_score'))
    if not flags['any_positive']:
        if score == 0 and source.get('rag_band') == 'Green':
            return route('no_action_indicated', 'valid_zero')
        return route('evidence_validation', 'evidence_limited')
    if not all_types:
        return route('evidence_validation', 'defect_types_unknown')
    if not positives or any(k not in readings and (_number(v, 100) or 0) > 0 for k, v in detail.items()):
        return route('evidence_validation', 'defect_types_unknown')
    # An aggregate max averaged over intervals lies between the largest
    # individual mean and their sum. Allow only the stored rounding precision.
    if (any(value and not (positives & GROUP_DEFECTS[k]) for k, value in groups.items())
            or drivers - positives
            or any(k not in GROUP_DEFECTS or not (positives & GROUP_DEFECTS[k])
                   for k in (source.get('observed_defect_groups') or []))
            or any(value is not None and (value > sum(readings[d] for d in GROUP_DEFECTS[k]) + .006
                       or value + .006 < max(readings[d] for d in GROUP_DEFECTS[k]))
                   for k, value in groups.items())):
        return route('engineer_assessment', 'evidence_conflict')
    surface_local_trigger = ((groups['localised_pct'] or 0) > 0
                            and groups['localised_pct'] >= policy['localised_threshold_pct']) or (
                            max(groups['dressing_pct'] or 0, groups['micro_pct'] or 0) > 0
                            and max(groups['dressing_pct'] or 0, groups['micro_pct'] or 0) >= policy['surface_threshold_pct'])
    if (flags['structural_observed'] or flags['edge_observed']) and surface_local_trigger:
        return route('engineer_assessment', 'mixed_deterioration')
    # Surface/local appraisal retains the existing conditional-candidate gate.
    # Structural/edge observations must be resolved before surface appraisal.
    if not flags['structural_observed'] and not flags['edge_observed'] and flags['candidate_trigger']:
        return route('treatment_appraisal', 'candidate_trigger')
    if score is None or source.get('rag_band') not in ('Green', 'Amber', 'Red'):
        return route('evidence_validation', 'evidence_limited')
    if source.get('rag_band') == 'Red' or score >= RAG_RED_THRESHOLD:
        return route('engineer_assessment', 'local_condition_concern')
    if (positives <= MINOR_DEFECTS and minor_sum < policy['acceptable_minor_extent_pct']
            and source.get('rag_band') == 'Green' and score < RAG_AMBER_THRESHOLD):
        return route('no_action_indicated', 'minor_acceptable')
    # Pothole depth and local risk are not established by small average extent.
    if 'Minor pothole' in positives:
        return route('engineer_assessment', 'positive_observations')
    if policy['automatic_monitoring_enabled']:
        return route('monitor', 'limited_deterioration')
    return route('engineer_assessment', 'positive_observations')
