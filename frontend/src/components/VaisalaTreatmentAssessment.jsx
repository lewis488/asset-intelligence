export default function VaisalaTreatmentAssessment({ assessment, scope, percentile, showAction = true }) {
  if (!assessment) return <p style={{ fontSize: 12, color: 'var(--muted)' }}>Treatment assessment unavailable. Refresh the survey view to load the current evidence assessment.</p>
  return (
    <div style={{ fontSize: 12, lineHeight: 1.6 }}>
      <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 6 }}>
        Evidence scope: {scope || 'section'}
        {percentile != null && <> · Relative priority percentile: {Number(percentile).toFixed(1)} (higher = worse within this scale)</>}
      </div>
      {showAction && <><div style={{ fontSize: 14, fontWeight: 700 }}>Next action: {assessment.action}</div>
      <p style={{ margin: '6px 0 12px' }}>{assessment.reason}</p></>}
      {assessment.evidence?.length > 0 && <>
        <strong>Observed evidence</strong>
        <ul style={{ margin: '4px 0 12px', paddingLeft: 18 }}>{assessment.evidence.map(item => <li key={item}>{item}</li>)}</ul>
      </>}
      {assessment.surface_only_caution && <p style={{ color: 'var(--color-amber)' }}>{assessment.surface_only_caution}</p>}
      <strong>Conditional treatment candidates</strong>
      {!assessment.candidates?.length && <p>No candidate selected from the available evidence.</p>}
      {assessment.candidates?.map(candidate => (
        <details key={candidate.name} style={{ marginTop: 8, padding: 10, border: '1px solid var(--color-border)', borderRadius: 6 }}>
          <summary style={{ cursor: 'pointer', fontWeight: 600 }}>{candidate.name}</summary>
          <p>{candidate.rationale}</p>
          <strong>Confirm before selection</strong>
          <ul style={{ paddingLeft: 18 }}>{candidate.prerequisites.map(item => <li key={item}>{item}</li>)}</ul>
          <strong>Limitations</strong>
          <ul style={{ paddingLeft: 18 }}>{candidate.cautions.map(item => <li key={item}>{item}</li>)}</ul>
        </details>
      ))}
      <details style={{ marginTop: 12 }}>
        <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Evidence still needed</summary>
        <ul style={{ paddingLeft: 18 }}>{assessment.evidence_gaps?.map(item => <li key={item}>{item}</li>)}</ul>
      </details>
      <p style={{ marginTop: 12, color: 'var(--muted)', fontSize: 11 }}>{assessment.screening_basis} Relative rank does not determine treatment suitability.</p>
    </div>
  )
}
