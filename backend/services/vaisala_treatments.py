"""Evidence-led screening for Vaisala view rows. Never changes scores or stored data."""
from collections import defaultdict
import math

from services.vaisala_scoring import (
    STRUCTURAL_THRESH, ALLIGATOR_TIER_THRESH, LOCALISED_THRESH, SURFACE_THRESH,
    RAG_VALIDATED_WEIGHTS, STRUCTURAL_KEYS, ALLIGATOR_KEY, LOCALISED_KEYS,
    DRESSING_KEYS, MICRO_KEYS, EDGE_KEYS,
)

MODEL_VERSION = 'vaisala-candidates-v1'
GROUPS = {
    'structural_pct': 'Structural-associated defects',
    'alligator_pct': 'Alligator cracking',
    'localised_pct': 'Localised defects',
    'dressing_pct': 'Dressing-related defects',
    'micro_pct': 'Micro-surfacing-related defects',
    'edge_pct': 'Edge deterioration',
}
ASSESSMENT_INPUTS = (*GROUPS, 'qc_completeness_pct', 'qc_reliability_pct',
                     'priority_score', 'rag_band', 'defect_proportions', 'defect_evidence_complete',
                     'primary_defect', 'primary_defect_contribution', 'secondary_defect', 'secondary_defect_contribution')
GROUP_DEFECTS = dict(zip(GROUPS, (STRUCTURAL_KEYS, {ALLIGATOR_KEY}, LOCALISED_KEYS,
                                DRESSING_KEYS, MICRO_KEYS, EDGE_KEYS)))


def _number(value, maximum=None):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0 or (maximum is not None and number > maximum):
        return None
    return number


def assess_treatments(row: dict) -> dict:
    """Consume whole percentages. Candidates are alternatives, not a design or cost appraisal.

    The original extent triggers are retained only for screening. Any structural
    indication warrants investigation, even below those triggers. No authority's
    traffic, policy, recurrence or pavement capacity is inferred from visual data.
    """
    values = {key: _number(row.get(key), 100) for key in GROUPS}
    detail = row.get('defect_proportions') or {}
    available = {key for key in RAG_VALIDATED_WEIGHTS if _number(detail.get(key), 100) is not None}
    complete_detail = row.get('defect_evidence_complete') is True
    # Legacy raw ingestion zeros absent columns. A zero aggregate is not proof
    # of absence where its underlying columns were not retained or supplied.
    for key, defects in GROUP_DEFECTS.items():
        if values[key] == 0 and not complete_detail and not defects <= available:
            values[key] = None
    evidence = [f'{GROUPS[k]}: {v:.1f}% (group measure)' for k, v in values.items() if v is not None and v > 0]
    missing = [GROUPS[k] for k, v in values.items() if v is None]
    gaps = ['Structural capacity, defect depth and drainage cause have not been established by this survey.',
            'Site inspection, repair recurrence and authority treatment policy are not supplied.']
    if missing:
        gaps.append('Missing or invalid defect measures: ' + ', '.join(missing) + '.')
    if not complete_detail:
        gaps.append('Complete valid defect readings are not established. Validate unobserved defect types; stored zeros may reflect absent or invalid source readings.')
    qc = [_number(row.get(key), 100) for key in ('qc_completeness_pct', 'qc_reliability_pct')]
    quality_limited = any(v is None or v < 85 for v in qc)
    if any(v is None for v in qc):
        gaps.append('Survey QC is incomplete or unknown; confirm coverage and validity.')
    if any(v is not None and v < 85 for v in qc):
        gaps.append('Survey QC is below the existing High band; validate observations and coverage.')

    candidates = []
    def candidate(name, rationale, prerequisites, cautions):
        candidates.append(dict(name=name, status='conditional', rationale=rationale,
                               prerequisites=prerequisites, cautions=cautions))

    structural_details = [key for key in (*STRUCTURAL_KEYS, ALLIGATOR_KEY)
                          if (_number(detail.get(key), 100) or 0) > 0]
    structural_drivers = [row.get(f'{position}_defect') for position in ('primary', 'secondary')
                          if row.get(f'{position}_defect') in STRUCTURAL_KEYS | {ALLIGATOR_KEY}
                          and (_number(row.get(f'{position}_defect_contribution')) or 0) > 0]
    partial_groups = set(row.get('observed_defect_groups') or [])
    structural = ((values['structural_pct'] or 0) > 0 or (values['alligator_pct'] or 0) > 0
                  or bool(structural_details) or bool(structural_drivers)
                  or bool(partial_groups & {'structural_pct', 'alligator_pct'}))
    for name in sorted(set(structural_drivers) - set(structural_details)):
        evidence.append(f'{name}: positive recorded score contribution; affected extent may be unknown.')
    for key in sorted(partial_groups & GROUPS.keys()):
        if values[key] is None:
            evidence.append(f'{GROUPS[key]}: positive observations in part of this extent; complete aggregate unavailable.')
    for key in sorted(structural_details):
        evidence.append(f'{key}: {float(detail[key]):.1f}% (individual defect)')
    local = values['localised_pct'] or 0
    edge = values['edge_pct'] or 0
    surface = max(values['dressing_pct'] or 0, values['micro_pct'] or 0)
    if structural:
        action = 'Investigate'
        reason = 'Structural-associated observations warrant investigation of the failure mechanism and depth.'
        if (values['structural_pct'] or 0) >= STRUCTURAL_THRESH * 100 or (values['alligator_pct'] or 0) >= ALLIGATOR_TIER_THRESH * 100:
            reason += ' Extent meets a legacy screening trigger; this does not prescribe resurfacing.'
        candidate('Localised deeper repair', reason,
                  ['Inspection confirms localised deterioration and establishes repair depth.',
                   'Review drainage, utilities and previous repairs.'],
                  ['Visual observations do not confirm structural failure or the affected layers.'])
        candidate('Strengthening / rehabilitation', 'A broader intervention may be appropriate if investigation confirms extensive deeper deterioration.',
                  ['Establish structural condition and extent through appropriate investigation.',
                   'Compare strengthening, deep inlay, recycling or reconstruction against authority policy and whole-life appraisal.'],
                  ['Do not select reconstruction from condition score or defect extent alone.'])
    else:
        action = 'Monitor'
        reason = 'No positive defect-group measures are recorded; continue routine monitoring and safety inspections. This does not establish sound structure.'

    if local >= LOCALISED_THRESH * 100:
        candidate('Localised patch repair', f'Localised defect group is {local:.1f}%, meeting the legacy screening trigger.',
                  ['Confirm defect locations, repair depth and whether defects are genuinely localised.',
                   'Check repair recurrence, drainage and utility history.'],
                  ['Repeated patching may not address the cause; do not assume it is the optimum long-term option.'])

    if edge > 0:
        candidate('Edge repair / haunching', f'Edge deterioration is recorded at {edge:.1f}%.',
                  ['Inspect lateral support, verge overrunning and drainage.',
                   'Confirm whether local reconstruction or drainage/verge work is needed.'],
                  ['A surface patch alone may not restore edge support.'])

    if surface >= SURFACE_THRESH * 100 and not structural:
        for name in ('Surface dressing', 'Micro-surfacing', 'Thin surfacing'):
            candidate(name, 'Surface-related defect extent meets a legacy screening trigger; compare alternatives after inspection.',
                      ['Confirm suitable pavement support, drainage, surface condition and defect mechanism.',
                       'Review texture/friction evidence where relevant, site constraints and authority treatment policy.'],
                      ['Missing structural observations do not establish sound pavement.',
                       'Defect-group dominance alone cannot select this treatment.'])

    if not structural:
        if candidates:
            action = 'Appraise maintenance options'
            reason = 'Compare the conditional options after confirming the observed defects and site requirements.'
        elif evidence:
            action = 'Inspect'
            reason = 'Defects are recorded below the existing extent triggers; inspect their local significance before selecting an intervention.'
        if missing or quality_limited or not complete_detail:
            action = 'Inspect'
            reason = 'Validate incomplete or limited-quality evidence before selecting treatment or concluding that monitoring is sufficient.'
        elif edge > 0:
            action = 'Inspect'
            reason = 'Inspect edge support and drainage to determine the appropriate repair.'
        if not evidence and (row.get('rag_band') in ('Red', 'Amber') or (_number(row.get('priority_score')) or 0) > 0):
            action = 'Inspect'
            reason = 'The condition score indicates deterioration but positive defect-group evidence is absent; reconcile the evidence before selecting treatment.'
            gaps.append('Condition score and available defect-group measures do not explain one another.')

    return dict(version=MODEL_VERSION, action=action, reason=reason, evidence=evidence,
                candidates=candidates, evidence_gaps=gaps,
                screening_basis='Legacy extent triggers are provisional screening defaults, not national treatment criteria. QC bands describe survey quality only.',
                surface_only_caution=('Structural-associated observations make surface-only treatment suitability unconfirmed.' if structural else None))


def assessment_fields(row: dict) -> dict:
    assessment = assess_treatments(row)
    summary = '; '.join(c['name'] for c in assessment['candidates']) or 'No candidate selected'
    return dict(treatment_assessment=assessment, recommended_action=assessment['action'],
                treatment=summary, candidate_summary=summary,
                assessment_reason=assessment['reason'],
                assessment_evidence='; '.join(assessment['evidence']) or 'No positive defect-group measures supplied',
                evidence_gaps='; '.join(assessment['evidence_gaps']),
                candidate_conditions=' | '.join(c['name'] + ': ' + '; '.join(c['prerequisites']) for c in assessment['candidates']),
                candidate_cautions=' | '.join(c['name'] + ': ' + '; '.join(c['cautions']) for c in assessment['candidates']),
                assessment_version=MODEL_VERSION)


def add_priority_percentiles(rows: list[dict]) -> None:
    """Mid-ranks for ties, within each effective scale. Singleton/unscored = unknown."""
    scopes = defaultdict(list)
    for row in rows:
        row['priority_percentile'] = None
        score = _number(row.get('priority_score'))
        if score is not None:
            scopes[row.get('assessment_scope', 'section')].append((score, row))
    for group in scopes.values():
        group.sort(key=lambda item: item[0])
        if len(group) < 2:
            continue
        start = 0
        while start < len(group):
            end = start + 1
            while end < len(group) and group[end][0] == group[start][0]:
                end += 1
            percentile = round(((start + end - 1) / 2) / (len(group) - 1) * 100, 2)
            for _, row in group[start:end]:
                row['priority_percentile'] = percentile
            start = end
