const reasons = {
  section_acceptable: 'Acceptable section extent; local flags separate',
  section_monitor: 'Section monitoring',
  section_appraisal: 'Section maintenance appraisal',
  section_investigation: 'Section engineering investigation',
  mixed_deterioration: 'Mixed deterioration needs assessment before treatment appraisal',
  significant_observation: 'Significant defect observations need local assessment',
  local_condition_concern: 'Section or local interval condition needs assessment',
  structural_extent: 'Structural-associated cracking reaches the policy extent trigger',
  defect_types_unknown: 'Individual defect types need validation',
  minor_acceptable: 'Minor observations within the policy acceptable extent',
  limited_deterioration: 'Limited deterioration needs a planned review',
  structural_observed: 'Positive structural-associated observations',
  edge_observed: 'Edge deterioration observations',
  evidence_conflict: 'Condition score and observations need reconciliation',
  evidence_limited: 'Missing or limited evidence needs validation',
  candidate_trigger: 'Conditional treatment appraisal trigger reached',
  positive_observations: 'Other positive observations need engineering assessment',
  valid_zero: 'Adequate valid observations indicate no additional intervention',
}

export default function VaisalaActionDiagnostics({ diagnostics }) {
  if (!diagnostics?.reason_counts) return null
  const extent = diagnostics.structural_group_extent || {}
  const proportionate = ['vaisala-programme-v2', 'vaisala-programme-v3', 'vaisala-programme-v3.1'].includes(diagnostics.model_version)
  return <details style={{ marginTop: 12, fontSize: 12, lineHeight: 1.65 }}>
    <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Why these actions?</summary>
    <p>Primary model routing reasons for these {diagnostics.total_items} assessed records. Each record has one primary reason; saved client decisions can change its working queue.</p>
    <ul>{Object.entries(reasons).map(([key, label]) => <li key={key}>{label}: <strong>{diagnostics.reason_counts[key] || 0}</strong></li>)}</ul>
    <p>{proportionate ? 'Actions consider defect type, severity, extent and evidence quality under the active policy. Significant local observations remain visible even at small section-average extents. ' : 'This historical model routes any positive structural-associated observation to engineer assessment. '}At section scale, a queue describes the next action for the section; it does not mean the whole section needs repair or that structural failure is confirmed.</p>
    {extent.known_count > 0 && <p>Largest recorded structural/alligator group measure per flagged record: {Number(extent.min_pct).toFixed(2)}%–{Number(extent.max_pct).toFixed(2)}% across {extent.known_count} records. These group measures can overlap and are not unique damaged length.</p>}
    {extent.unknown_count > 0 && <p>{extent.unknown_count} structural-associated records have no positive aggregate group extent available; their trigger comes from other recorded observations.</p>}
    <p>Complete valid readings not established: <strong>{diagnostics.incomplete_readings_count}</strong>. QC below the policy requirement or unknown: <strong>{diagnostics.limited_qc_count}</strong>. These checks can overlap and do not add records.</p>
    <p>{proportionate ? 'The severity/extent policy can route limited deterioration to monitoring and adequately evidenced minor observations to no intervention. Thresholds are provisional authority screening choices, not national intervention criteria. Monitoring requires a planned review under authority inspection policy. Current section views separate maintenance appraisal from local flags under all policy versions; saved programmes retain their recorded decisions.' : 'This historical model requires a documented client decision for monitoring and adequate valid zero observations for no intervention.'} Routine inspection obligations continue. Empty queues are shown; no quota is used to populate them.</p>
  </details>
}
