function ScoreBar({ value, max = 185 }) {
  const pct = Math.min(100, ((value || 0) / max) * 100)
  const colour = pct >= 65 ? 'var(--critical)' : pct >= 40 ? 'var(--high)' : pct >= 20 ? 'var(--medium)' : 'var(--low)'
  return (
    <div className="score-bar-wrap">
      <div className="score-bar-track">
        <div className="score-bar-fill" style={{ width: `${pct}%`, background: colour }} />
      </div>
      <span className="score-bar-val">{(value || 0).toFixed(0)}</span>
    </div>
  )
}

const urgencyColour = (u) => {
  if (!u) return 'var(--muted)'
  if (u === 'Immediate')           return 'var(--critical)'
  if (u === 'This financial year') return 'var(--high)'
  if (u.startsWith('Programme'))   return 'var(--medium)'
  return 'var(--low)'
}

export default function PriorityList({ assets, loading, onRowClick, selectedNsgRef }) {
  if (loading) return <div style={{ padding: 24, textAlign: 'center' }}><span className="spinner" /></div>
  if (!assets?.length) return (
    <div style={{ padding: 36, textAlign: 'center', color: 'var(--muted)' }}>
      No assets to display. Upload SCANNER, CVI, or reactive data.
    </div>
  )

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="data-table">
        <thead>
          <tr>
            <th>#</th>
            <th>NSG Ref</th>
            <th>Road Name</th>
            <th>Parish</th>
            <th>Class</th>
            <th>CI</th>
            <th>RCI</th>
            <th>Risk</th>
            <th style={{ minWidth: 110 }}>Score</th>
            <th>Datasets</th>
            <th>Treatment</th>
            <th>Urgency</th>
          </tr>
        </thead>
        <tbody>
          {assets.map((a, i) => (
            <tr
              key={a.id ?? a.nsg_ref ?? i}
              className={`row-clickable${a.nsg_ref === selectedNsgRef ? ' row-selected' : ''}`}
              onClick={() => onRowClick?.(a)}
            >
              <td style={{ color: 'var(--muted)' }}>{i + 1}</td>
              <td><code style={{ fontFamily: 'monospace', fontSize: 11.5 }}>{a.nsg_ref}</code></td>
              <td>{a.road_name || <span style={{ color: 'var(--muted)' }}>—</span>}</td>
              <td style={{ color: 'var(--muted)', fontSize: 12 }}>{a.parish || '—'}</td>
              <td><span className="badge badge-Unknown">{a.road_class || '—'}</span></td>
              <td><strong>{a.scanner_data?.avg_ci?.toFixed(1) ?? '—'}</strong></td>
              <td>
                {a.scanner_data?.rci_band
                  ? <span className={`badge badge-${a.scanner_data.rci_band}`}>{a.scanner_data.rci_band}</span>
                  : '—'}
              </td>
              <td><span className={`badge badge-${a.risk_band}`}>{a.risk_band}</span></td>
              <td><ScoreBar value={a.composite_score} /></td>
              <td style={{ fontSize: 11 }}>
                {[a.has_scanner && 'S', a.has_cvi && 'C', a.has_scrim && 'R', a.has_reactive && 'J']
                  .filter(Boolean)
                  .map(d => (
                    <span key={d} style={{ display: 'inline-block', marginRight: 2, padding: '1px 5px', borderRadius: 3, background: 'var(--color-blue-dim)', color: 'var(--color-blue)', fontWeight: 700, border: '1px solid rgba(59,130,246,0.2)', fontSize: 11 }}>
                      {d}
                    </span>
                  ))}
              </td>
              <td style={{ maxWidth: 180, fontSize: 12, color: 'var(--muted)' }}>
                {a.treatment_recommendation || '—'}
              </td>
              <td style={{ fontSize: 12, fontWeight: 600, color: urgencyColour(a.urgency) }}>
                {a.urgency || '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
