"""Section maintenance screening and separate local observations.

Policy limits are screening thresholds, not measured damaged road lengths or
national intervention criteria. Local observations never establish whole-section
structural failure.
"""
from services.vaisala_scoring import RAG_VALIDATED_WEIGHTS, RAG_RED_THRESHOLD
from services.vaisala_treatments import GROUP_DEFECTS, _number
import json
import math
from collections import defaultdict

LOCAL_TYPES = frozenset({'Subsidence', 'Minor pothole', 'Moderate pothole', 'Severe pothole',
    'Severe longitudinal cracking', 'Severe transverse cracking', 'Wheel track cracking',
    'Alligator cracking', 'Binder bleeding', 'Left edge deterioration', 'Right edge deterioration'})


def local_defect_flags(row):
    """Retain positive observations, including when maintenance evidence is limited."""
    detail = row.get('defect_proportions') or {}
    names = {k for k in LOCAL_TYPES if (_number(detail.get(k), 100) or 0) > 0}
    for prefix in ('primary', 'secondary'):
        if (_number(row.get(f'{prefix}_defect_contribution')) or 0) > 0:
            name = row.get(f'{prefix}_defect')
            if name in LOCAL_TYPES:
                names.add(name)
    flags = [dict(defect=name, section_measure_pct=_number(detail.get(name), 100),
                  locations=[], location_status='Source interval location unavailable; review original survey')
             for name in sorted(names)]
    for group in ('structural_pct', 'alligator_pct', 'localised_pct', 'edge_pct'):
        if (_number(row.get(group), 100) or 0) > 0 and not names.intersection(GROUP_DEFECTS[group]):
            flags.append(dict(defect=group.replace('_pct', '').capitalize() + ' group observation',
                section_measure_pct=_number(row.get(group), 100), locations=[],
                location_status='Individual defect type and location require source review'))
    if (_number(row.get('worst_interval_score')) or 0) >= RAG_RED_THRESHOLD:
        flags.append(dict(defect='Red interval condition', locations=[],
                          location_status='Source interval location unavailable; review original survey'))
    return flags


def attach_local_locations(rows, intervals):
    """Join only intervals from the caller's authorised survey, by NSG and subref."""
    locations = defaultdict(lambda: defaultdict(list))
    for iv in intervals:
        extras = iv.get('extras_json') or '{}'
        try:
            extras = json.loads(extras) if isinstance(extras, str) else extras
        except (ValueError, TypeError):
            extras = {}
        if not isinstance(extras, dict):
            extras = {}
        detail = extras.get('defect_proportions') or {}
        observed = {k for k in LOCAL_TYPES if (_number(detail.get(k), 100) or 0) > 0}
        if iv.get('primary_defect') in LOCAL_TYPES and (_number(iv.get('primary_defect_contribution')) or 0) > 0:
            observed.add(iv['primary_defect'])
        if (_number(iv.get('interval_score')) or 0) >= RAG_RED_THRESHOLD:
            observed.add('Red interval condition')
        for name in sorted(observed):
            locations[iv['section_ref']][name].append(dict(net_reference=iv.get('net_reference'),
                from_m=iv.get('from_m'), to_m=iv.get('to_m'), interval_id=iv.get('id'),
                interval_measure_pct=_number(detail.get(name), 100)))
    for row in rows:
        if row.get('assessment_scope', 'section') != 'section':
            continue
        flags = {f['defect']: f for f in local_defect_flags(row)}
        for name, spans in locations[row['section_ref']].items():
            flag = flags.setdefault(name, dict(defect=name, locations=[]))
            flag['locations'] = spans
            flag['location_status'] = ('Located in source intervals' if all(
                _number(s['from_m']) is not None and _number(s['to_m']) is not None
                and s['to_m'] > s['from_m'] for s in spans)
                else 'Some source locations unavailable; re-import original workbook to recover chainage')
        row['local_defect_flags'] = list(flags.values())


def section_action(row, flags, policy):
    detail = row.get('defect_proportions') or {}
    readings = {k: _number(detail.get(k), 100) for k in RAG_VALIDATED_WEIGHTS}
    evidence = dict(section_extent_upper_bound_pct=math.fsum(v or 0 for v in readings.values()),
                    local_flags_separate=True)
    def result(action, reason):
        return action, reason, evidence
    if (not flags['complete_readings'] or not flags['qc_adequate'] or flags['evidence_conflict']
            or _number(row.get('priority_score')) is None
            or row.get('rag_band') not in ('Green', 'Amber', 'Red')
            or any(v is None for v in readings.values())):
        return result('evidence_validation', 'evidence_limited')
    groups = {k: _number(row.get(k), 100) for k in GROUP_DEFECTS}
    # Check compatible group/individual summaries, allowing stored rounding.
    if any(v is None or v > sum(readings[d] for d in GROUP_DEFECTS[k]) + .006
           or v + .006 < max(readings[d] for d in GROUP_DEFECTS[k]) for k, v in groups.items()):
        return result('evidence_validation', 'evidence_conflict')
    structural = max(groups['structural_pct'], groups['alligator_pct'])
    substantial_structure = structural > 0 and structural >= policy['structural_assessment_pct']
    substantial_edge = groups['edge_pct'] > 0 and groups['edge_pct'] >= policy['edge_assessment_pct']
    appraisal = (substantial_structure or substantial_edge
        or groups['localised_pct'] > 0 and groups['localised_pct'] >= policy['localised_threshold_pct']
        or max(groups['micro_pct'], groups['dressing_pct']) > 0
        and max(groups['micro_pct'], groups['dressing_pct']) >= policy['surface_threshold_pct'])
    if row['rag_band'] != 'Green' and (substantial_structure or substantial_edge):
        return result('engineer_assessment', 'section_investigation')
    if appraisal or row['rag_band'] != 'Green':
        return result('treatment_appraisal', 'section_appraisal')
    if evidence['section_extent_upper_bound_pct'] == 0 or evidence['section_extent_upper_bound_pct'] < policy['acceptable_minor_extent_pct']:
        return result('no_action_indicated', 'section_acceptable')
    return result('monitor', 'section_monitor')
