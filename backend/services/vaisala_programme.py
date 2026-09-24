"""Deterministic Vaisala action queues. No condition scoring or database writes."""
from collections import defaultdict
import hashlib
import json

from services.vaisala_treatments import assess_treatments, add_priority_percentiles, _number

MODEL_VERSION = 'vaisala-programme-v1'
DEFAULT_POLICY = dict(version='vaisala-programme-default-v1', localised_threshold_pct=5,
                      surface_threshold_pct=5, qc_adequacy_pct=85, automatic_monitoring_enabled=False)
ACTIONS = {
    'engineer_assessment': 'Engineer assessment',
    'evidence_validation': 'Validate evidence / further survey',
    'treatment_appraisal': 'Treatment appraisal',
    'monitor': 'Monitor observed deterioration',
    'no_action_indicated': 'No intervention indicated by this survey',
}
BRIEFS = {
    'structural_observed': ('Review the recorded structural-associated observations. Establish the failure mechanism and depth; determine whether targeted investigation is needed before appraising repair.', 'Is deterioration confined to the surface, or does it involve deeper layers?'),
    'edge_observed': ('Inspect the recorded edge deterioration, lateral support and drainage before selecting a repair.', 'What is causing the edge deterioration and what support or drainage work is needed?'),
    'evidence_conflict': ('Reconcile the condition score with the available defect observations using the original survey evidence.', 'Which observations explain the recorded condition score?'),
    'evidence_limited': ('Check original survey readings, available imagery and coverage. If the gap cannot be resolved, arrange targeted verification of this extent.', 'Can the missing or uncertain evidence be resolved from the original survey, or is further inspection or survey needed?'),
    'candidate_trigger': ('Inspect the observed defects and compare the conditional treatment options against their prerequisites and site requirements.', 'Which candidate is suitable once pavement support, defect mechanism and site requirements have been confirmed?'),
    'positive_observations': ('Inspect the recorded defects to establish their local significance before selecting an intervention or a monitoring decision.', 'Do these observations require intervention, further investigation or monitoring?'),
    'valid_zero': ('No additional condition-led intervention is indicated by these observations. Continue existing inspection obligations.', 'Do subsequent inspections or surveys identify a change requiring reassessment?'),
}


def validate_policy(policy: dict) -> dict:
    if not isinstance(policy, dict) or set(policy) - set(DEFAULT_POLICY):
        raise ValueError('Unknown programme policy fields')
    result = {**DEFAULT_POLICY, **policy}
    if not isinstance(result['version'], str) or not result['version'].strip():
        raise ValueError('Policy version is required')
    for field in ('localised_threshold_pct', 'surface_threshold_pct', 'qc_adequacy_pct'):
        if _number(result[field], 100) is None:
            raise ValueError(f'{field} must be a finite percentage between 0 and 100')
        result[field] = float(result[field])
    if result['automatic_monitoring_enabled'] is not False:
        raise ValueError('Automatic monitoring requires a separately validated rule; use a recorded client review')
    if result['qc_adequacy_pct'] < 85:
        raise ValueError('QC adequacy cannot be below the existing High boundary of 85')
    return result


def programme_item(row: dict, *, survey_id: int, policy: dict) -> dict:
    policy = validate_policy(policy)
    source = dict(row)
    # The legacy interval view fills absent scores for display. Programme ranking
    # uses the source validity marker and never promotes an invented zero.
    if source.get('source_score_valid') is False:
        source['priority_score'] = None
        source['rag_band'] = None
    assessment = assess_treatments(source, policy=policy)
    flags = assessment['evidence_flags']
    limited = not flags['complete_readings'] or not flags['qc_adequate']
    if flags['structural_observed']:
        action, reason = 'engineer_assessment', 'structural_observed'
    elif flags['edge_observed']:
        action, reason = 'engineer_assessment', 'edge_observed'
    elif flags['evidence_conflict']:
        action, reason = 'engineer_assessment', 'evidence_conflict'
    elif limited:
        action, reason = 'evidence_validation', 'evidence_limited'
    elif flags['candidate_trigger']:
        action, reason = 'treatment_appraisal', 'candidate_trigger'
    elif flags['any_positive']:
        action, reason = 'engineer_assessment', 'positive_observations'
    elif _number(source.get('priority_score')) == 0 and source.get('rag_band') == 'Green':
        action, reason = 'no_action_indicated', 'valid_zero'
    else:
        action, reason = 'evidence_validation', 'evidence_limited'
        limited = True
    scope = source.get('assessment_scope') or 'section'
    identity = [survey_id, scope, source.get('section_ref'), source.get('net_reference'),
                sorted(source.get('source_interval_ids') or []),
                (source.get('narrative_section_id') or source.get('id')) if scope == 'section' and not source.get('source_interval_ids') else None]
    if scope != 'section' and not source.get('source_interval_ids'):
        identity.append([source.get('from_m'), source.get('to_m'), source.get('id')])
    key = hashlib.sha256(json.dumps(identity, separators=(',', ':')).encode()).hexdigest()[:32]
    brief, question = BRIEFS[reason]
    evidence_status = 'conflicting' if flags['evidence_conflict'] else ('limited' if limited else 'adequate')
    # Keep candidates reusable, while avoiding contradictory old action headings.
    assessment = {**assessment, 'action': ACTIONS[action], 'reason': brief}
    result = {**source, 'survey_id': survey_id, 'item_key': key, 'assessment_scope': scope,
            'model_version': MODEL_VERSION, 'policy_version': policy['version'],
            'recommended_action': action, 'action_label': ACTIONS[action], 'reason_codes': [reason],
            'brief': brief, 'next_question': question,
            'prerequisite_tasks': ['validate_evidence'] if limited else [],
            'evidence_status': evidence_status, 'treatment_assessment': assessment,
            'queue_rank': None, 'queue_size': 0, 'validation_order': None,
            'priority_explanation': 'No condition priority assigned.', 'review_status': 'unreviewed',
            'parent_section_id': None if source.get('section_summary_recovered') else (source.get('narrative_section_id') or (source.get('id') if scope == 'section' else None)),
            'evidence_flags': flags, 'limitations': assessment['evidence_gaps'],
            'treatment_candidates': assessment['candidates']}
    known_length, unresolved = _coverage([result])
    result['assessed_length_m'] = known_length if not unresolved else None
    result['known_length_m'] = known_length
    result['unresolved_extents'] = unresolved
    result['length_basis'] = ('section coverage' if scope == 'section' and not source.get('source_interval_ids') else 'union of source chainage extents') if not unresolved else 'unresolved source extent; known coverage only'
    return result


def _coverage(items: list[dict]) -> tuple[float, int]:
    sections, intervals = {}, defaultdict(list)
    unresolved = 0
    for item in items:
        section = str(item.get('section_ref') or item['item_key'])
        if item['assessment_scope'] == 'section' and not item.get('source_interval_ids'):
            length = _number(item.get('length_m'))
            if length is None or length <= 0:
                unresolved += 1
            else:
                sections[section] = max(sections.get(section, 0), length)
            continue
        extents = item.get('source_extents') or [{'from_m': item.get('from_m'), 'to_m': item.get('to_m')}]
        for extent in extents:
            start, end = _number(extent.get('from_m')), _number(extent.get('to_m'))
            if start is None or end is None or end <= start:
                unresolved += 1
            else:
                intervals[(section, extent.get('net_reference') or item.get('net_reference') or '')].append((start, end))
    total = sum(sections.values())
    for (section, _), spans in intervals.items():
        if section in sections:
            continue
        end_seen = None
        for start, end in sorted(spans):
            total += end - start if end_seen is None else max(0, end - max(start, end_seen))
            end_seen = max(end_seen or 0, end)
    return round(total, 3), unresolved


def action_diagnostics(items: list[dict]) -> dict:
    """Explain model queue distribution without inventing new intervention thresholds."""
    counts = {reason: 0 for reason in BRIEFS}
    extents = []
    structural_total = incomplete = limited_qc = 0
    for item in items:
        for reason in item.get('reason_codes', []):
            counts[reason] = counts.get(reason, 0) + 1
        flags = item.get('evidence_flags') or item.get('treatment_assessment', {}).get('evidence_flags', {})
        incomplete += not flags.get('complete_readings', False)
        limited_qc += not flags.get('qc_adequate', False)
        if flags.get('structural_observed'):
            structural_total += 1
            positive = [v for key in ('structural_pct', 'alligator_pct')
                        if (v := _number(item.get(key), 100)) is not None and v > 0]
            if positive:
                extents.append(max(positive))
    return dict(total_items=len(items), reason_counts=counts,
                incomplete_readings_count=incomplete, limited_qc_count=limited_qc,
                structural_group_extent=dict(known_count=len(extents),
                    unknown_count=structural_total-len(extents),
                    min_pct=min(extents) if extents else None,
                    max_pct=max(extents) if extents else None))


def build_programme(rows: list[dict], *, survey_id: int, policy: dict) -> dict:
    policy = validate_policy(policy)
    items = [programme_item(row, survey_id=survey_id, policy=policy) for row in rows]
    add_priority_percentiles(items)
    groups = defaultdict(list)
    scope_sizes = defaultdict(int)
    for item in items:
        groups[(item['assessment_scope'], item['recommended_action'])].append(item)
        if _number(item.get('priority_score')) is not None:
            scope_sizes[item['assessment_scope']] += 1
    cohorts = []
    for (scope, action), group in sorted(groups.items()):
        scored = sorted((r for r in group if _number(r.get('priority_score')) is not None),
                        key=lambda r: (-float(r['priority_score']), r['item_key']))
        ranks = {}
        for position, item in enumerate(scored, 1):
            ranks.setdefault(float(item['priority_score']), position)
        if action == 'evidence_validation':
            ordered = sorted(group, key=lambda r: (
                not r['treatment_assessment']['evidence_flags']['any_positive'],
                _number(r.get('priority_score')) is None,
                -(_number(r.get('priority_score')) or 0), r['item_key']))
            for order, item in enumerate(ordered, 1):
                item['validation_order'] = order
        for item in group:
            item['queue_size'] = len(scored)
            item['queue_total'] = len(group)
            item['percentile_cohort_size'] = scope_sizes[scope]
            item['priority_cohort_size'] = scope_sizes[scope]
            score = _number(item.get('priority_score'))
            if action in ('engineer_assessment', 'treatment_appraisal') and score is not None:
                item['queue_rank'] = ranks[score]
                item['priority_explanation'] = f"Condition rank {ranks[score]} of {len(scored)} scored lengths in {ACTIONS[action]}, {scope} view; score {score:g}. Equal scores share a rank."
            elif action == 'evidence_validation':
                item['priority_explanation'] = 'Validation order: known positive observations first, then available condition score. This is not a safety or urgency rank.'
            elif score is None:
                item['priority_explanation'] = 'Condition score unavailable; retained as unranked.'
        length, unresolved = _coverage(group)
        cohorts.append(dict(assessment_scope=scope, action=action, total_items=len(group), scored_items=len(scored), known_length_m=length, unresolved_extents=unresolved))
    items.sort(key=lambda r: (r['assessment_scope'], list(ACTIONS).index(r['recommended_action']),
                             r['validation_order'] or r['queue_rank'] or float('inf'), r['item_key']))
    length, unresolved = _coverage(items)
    action_counts, action_lengths = {}, {}
    for action in ACTIONS:
        subset = [r for r in items if r['recommended_action'] == action]
        action_counts[action] = len(subset)
        action_lengths[action] = _coverage(subset)[0]
    return dict(model_version=MODEL_VERSION, policy_version=policy['version'], survey_id=survey_id,
                policy=policy, cohorts=cohorts, items=items,
                summary=dict(total_items=len(items), known_length_m=length, unresolved_extents=unresolved,
                             action_counts=action_counts, action_lengths_m=action_lengths,
                             action_diagnostics=action_diagnostics(items),
                             coverage_note='Assessed coverage, not treatment quantity. Queue lengths may overlap; overall coverage is calculated independently.'))
