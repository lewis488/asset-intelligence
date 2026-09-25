"""Deterministic Vaisala action queues. No condition scoring or database writes."""
from collections import defaultdict
import hashlib
import json

from services.vaisala_treatments import assess_treatments, add_priority_percentiles, _number
from services.vaisala_action_rules import proportionate_action
from services.vaisala_section_appraisal import section_action, local_defect_flags

MODEL_VERSION = 'vaisala-programme-v3'
LEGACY_DEFAULT_POLICY = dict(version='vaisala-programme-default-v1', localised_threshold_pct=5,
                      surface_threshold_pct=5, qc_adequacy_pct=85, automatic_monitoring_enabled=False)
DEFAULT_POLICY = dict(version='vaisala-programme-default-v2', localised_threshold_pct=5,
                      surface_threshold_pct=5, qc_adequacy_pct=85, automatic_monitoring_enabled=True,
                      routing_rules='severity_extent_v2', acceptable_minor_extent_pct=1,
                      structural_assessment_pct=5, edge_assessment_pct=5)
ACTIONS = {
    'engineer_assessment': 'Engineer assessment',
    'evidence_validation': 'Validate evidence / further survey',
    'treatment_appraisal': 'Treatment appraisal',
    'monitor': 'Monitor observed deterioration',
    'no_action_indicated': 'No intervention indicated by this survey',
}
BRIEFS = {
    'section_acceptable': ('Section maintenance: acceptable within the authority screening tolerance; no section-wide intervention indicated. Local defect flags require separate review and remain subject to routine safety inspection.', 'Do local inspections or subsequent surveys identify a change?'),
    'section_monitor': ('Section maintenance: deterioration is below the maintenance appraisal triggers. Record a monitoring review. Assess local defect flags separately under authority inspection policy.', 'Who will review change in section condition, and when?'),
    'section_appraisal': ('Section maintenance: compare proportionate maintenance options for the observed extent. Confirm local defect locations, mechanism and repair needs before selecting a treatment; the full section is not a repair quantity.', 'Which maintenance option addresses the observed extent once local prerequisites are confirmed?'),
    'section_investigation': ('Section maintenance: elevated section condition and structural-associated or edge extent warrant engineering assessment. Confirm mechanism, support and affected lengths before selecting an intervention.', 'What investigation is needed to appraise the affected lengths?'),
    'mixed_deterioration': ('Surface or localised deterioration reaches its appraisal trigger alongside structural-associated or edge observations. Resolve the mixed defect mechanism and locations before appraising treatment.', 'Can targeted repairs address the local concerns before a surface option is considered?'),
    'significant_observation': ('Review the significant defect observation at its recorded location, even where its section-average extent is small. Establish local severity, mechanism and any response required under authority inspection policy.', 'What local investigation or response is warranted by this observation?'),
    'local_condition_concern': ('Review the recorded condition concern, including any worse interval within the section. Establish the affected location and extent before selecting an action; the whole section is not a repair quantity.', 'Does the local evidence require investigation or a targeted maintenance option?'),
    'structural_extent': ('Structural-associated cracking reaches the policy assessment trigger. Review its location, mechanism and depth before appraising repair; this is not a diagnosis of structural failure.', 'What mechanism and affected lengths explain the recorded cracking?'),
    'defect_types_unknown': ('Validate the individual defect types and severities before concluding that the observed deterioration is minor enough for routine inspection or monitoring.', 'Can the original readings or imagery establish the defect types and local severity?'),
    'minor_acceptable': ('Only minor cracking or moderate fretting is recorded below the policy acceptable-extent limit. No additional condition-led intervention is indicated by this survey. Continue routine inspections; this does not establish safety or structural soundness.', 'Do subsequent inspections identify deterioration beyond the authority tolerance?'),
    'limited_deterioration': ('Recorded deterioration is below the applicable action triggers. Arrange a documented review of the observed locations under the authority inspection policy, checking change in extent or severity and escalating if needed. Continue routine safety inspections.', 'Who will review the observed deterioration, and when under the authority inspection policy?'),
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
    # Old stored authority policies keep their original routing until explicitly
    # replaced; saved programmes are immutable and are never reassessed here.
    if 'routing_rules' not in policy:
        result['routing_rules'] = 'legacy_v1'
    if result['routing_rules'] not in ('legacy_v1', 'severity_extent_v2'):
        raise ValueError('Unknown routing rules')
    for field in ('localised_threshold_pct', 'surface_threshold_pct', 'qc_adequacy_pct',
                  'acceptable_minor_extent_pct', 'structural_assessment_pct', 'edge_assessment_pct'):
        if _number(result[field], 100) is None:
            raise ValueError(f'{field} must be a finite percentage between 0 and 100')
        result[field] = float(result[field])
    if not isinstance(result['automatic_monitoring_enabled'], bool):
        raise ValueError('Automatic monitoring must be a boolean')
    if result['routing_rules'] == 'legacy_v1' and result['automatic_monitoring_enabled']:
        raise ValueError('Automatic monitoring requires severity_extent_v2 routing')
    if result['routing_rules'] == 'severity_extent_v2' and result['acceptable_minor_extent_pct'] > result['surface_threshold_pct']:
        raise ValueError('Acceptable minor extent cannot exceed the surface appraisal threshold')
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
    action_evidence = {}
    if source.get('assessment_scope', 'section') == 'section':
        action, reason, action_evidence = section_action(source, flags, policy)
        limited = action == 'evidence_validation' or limited
    elif policy['routing_rules'] == 'severity_extent_v2':
        action, reason, action_evidence = proportionate_action(source, flags, policy)
        if action == 'evidence_validation':
            limited = True
    elif flags['structural_observed']:
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
    if reason == 'minor_acceptable':
        brief += f" Combined minor-defect screening upper bound {action_evidence['minor_extent_upper_bound_pct']:g}% < {policy['acceptable_minor_extent_pct']:g}%; overlapping observations are not unique damaged length."
    if reason == 'structural_extent':
        brief += f" Policy structural assessment trigger: {policy['structural_assessment_pct']:g}%."
    if reason == 'edge_observed' and policy['routing_rules'] == 'severity_extent_v2':
        brief += f" Policy edge assessment trigger: {policy['edge_assessment_pct']:g}%; unknown severity still requires assessment."
    if action in ('monitor', 'no_action_indicated'):
        assessment = {**assessment, 'candidates': []}
    if policy['routing_rules'] == 'severity_extent_v2':
        assessment = {**assessment, 'screening_basis': 'Severity and extent screening uses provisional authority policy, not calibrated national intervention criteria or CVI indices. QC describes survey quality, not diagnostic certainty.',
                      'action_evidence': action_evidence, 'action_policy': dict(policy)}
        if reason == 'defect_types_unknown':
            assessment = {**assessment, 'evidence_gaps': [*assessment['evidence_gaps'], 'Individual defect types are unavailable; group totals cannot establish minor-only deterioration.']}
    evidence_status = 'conflicting' if reason == 'evidence_conflict' else ('limited' if limited else 'adequate')
    # Keep candidates reusable, while avoiding contradictory old action headings.
    assessment = {**assessment, 'action': ACTIONS[action], 'reason': brief}
    if scope == 'section':
        local_flags = source.get('local_defect_flags', local_defect_flags(source))
        assessment = {**assessment, 'maintenance_scope': 'section', 'local_defect_flags': local_flags,
            'action_evidence': action_evidence,
            'screening_basis': 'Section maintenance and local defect review are separate. Extents are weighted survey measures, not unique damaged lengths. Most-severe interval exports are not averages of the original 5 m readings. Authority thresholds are provisional screening policy, not CVI indices.'}
        if action == 'evidence_validation':
            assessment['candidates'] = []
        if action == 'treatment_appraisal':
            assessment['candidates'] = [dict(name='Appraise maintenance for the affected extent', status='conditional',
                rationale=brief, prerequisites=['Review local defect flags and source imagery.',
                'Confirm repair depth, pavement support, drainage and suitable surface options at site.',
                'Compare targeted repair and wider maintenance under authority policy.'],
                cautions=['A Green section can still contain local defects requiring attention.',
                          'No specific treatment or whole-section repair quantity is prescribed.'])]
    result = {**source, 'survey_id': survey_id, 'item_key': key, 'assessment_scope': scope,
            'model_version': MODEL_VERSION, 'policy_version': policy['version'],
            'recommended_action': action, 'action_label': ACTIONS[action], 'reason_codes': [reason],
            'brief': brief, 'next_question': question,
            'prerequisite_tasks': (['validate_evidence'] if limited else []) + (['record_monitoring_review'] if action == 'monitor' else []),
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
    return dict(model_version=MODEL_VERSION, total_items=len(items), reason_counts=counts,
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
