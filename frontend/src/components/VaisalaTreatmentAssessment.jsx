export default function VaisalaTreatmentAssessment({ assessment, scope, percentile, showAction = true }) {
  if (!assessment) return <p style={{ fontSize: 12, color: 'var(--muted)' }}>Treatment assessment unavailable. Refresh the survey view to load the current evidence assessment.</p>
  return (
    <div style={{ fontSize: 12, lineHeight: 1.6 }}>
      <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 6 }}>
        Evidence scope: {scope || 'section'}
        {percentile != null && <> · Relative priority percentile: {Number(percentile).toFixed(1)} (higher = worse within this scale)</>}
      </div>
      {showAction && <><div style={{ fontSize: 14, fontWeight: 700 }}>{assessment.maintenance_scope === 'section' ? 'Section maintenance' : 'Next action'}: {assessment.action}</div>
      <p style={{ margin: '6px 0 12px' }}>{assessment.reason}</p></>}
      {assessment.local_defect_flags?.length > 0 && <div style={{ border: '1px solid var(--color-amber)', padding: 10, marginBottom: 12 }}>
        <strong>Local defect review — separate from section maintenance</strong>
        <p>A Green section or no section-wide intervention does not clear these local observations. Review imagery and inspect under the authority’s response policy.</p>
        {assessment.local_defect_flags.map(flag => <details key={flag.defect} style={{ marginTop: 6 }}>
          <summary>{flag.defect}{flag.section_measure_pct != null ? ` · section measure ${Number(flag.section_measure_pct).toFixed(4)}%` : ''} · {flag.locations?.length || 0} recorded intervals</summary>
          <p>{flag.location_status}</p>
          <ul>{flag.locations?.map((location, index) => <li key={location.interval_id ?? index}>
            {location.net_reference || 'Sub-section reference unavailable'} · {location.from_m != null && location.to_m != null ? `${Number(location.from_m).toFixed(1)}–${Number(location.to_m).toFixed(1)} m` : 'Chainage unavailable'}
            {location.interval_measure_pct != null ? ` · interval measure ${Number(location.interval_measure_pct).toFixed(4)}%` : ''}
          </li>)}</ul>
        </details>)}
      </div>}
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
