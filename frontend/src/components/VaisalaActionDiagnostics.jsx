const reasons = {
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
  return <details style={{ marginTop: 12, fontSize: 12, lineHeight: 1.65 }}>
    <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Why these actions?</summary>
    <p>Primary model routing reasons for these {diagnostics.total_items} assessed records. Each record has one primary reason; saved client decisions can change its working queue.</p>
    <ul>{Object.entries(reasons).map(([key, label]) => <li key={key}>{label}: <strong>{diagnostics.reason_counts[key] || 0}</strong></li>)}</ul>
    <p>Any positive structural-associated observation currently triggers engineer assessment. At section scale, that assigns the whole section to the queue; it does not mean the whole section needs repair or that structural failure is confirmed.</p>
    {extent.known_count > 0 && <p>Largest recorded structural/alligator group measure per flagged record: {Number(extent.min_pct).toFixed(2)}%–{Number(extent.max_pct).toFixed(2)}% across {extent.known_count} records. These group measures can overlap and are not unique damaged length.</p>}
    {extent.unknown_count > 0 && <p>{extent.unknown_count} structural-associated records have no positive aggregate group extent available; their trigger comes from other recorded observations.</p>}
    <p>Complete valid readings not established: <strong>{diagnostics.incomplete_readings_count}</strong>. QC below the policy requirement or unknown: <strong>{diagnostics.limited_qc_count}</strong>. These checks can overlap and do not add records.</p>
    <p>Monitor requires a documented client decision. No intervention indicated requires adequate valid zero observations and a consistent condition score. Empty queues are shown; no quota is used to populate them.</p>
  </details>
}
