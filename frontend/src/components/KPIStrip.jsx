function KPI({ label, value, sub, variant, wide }) {
  return (
    <div className={`kpi-card${variant ? ` ${variant}` : ''}${wide ? ' kpi-wide' : ''}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value ?? '—'}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  )
}

function pct(n) {
  if (n == null) return null
  return `${n.toFixed(1)}%`
}

function km(n) {
  if (n == null || n === 0) return '—'
  return `${n.toFixed(1)} km`
}

function fmt(n) {
  return n == null ? '—' : n.toLocaleString()
}

export default function KPIStrip({ stats, loading }) {
  if (loading && !stats) return (
    <div>
      <div className="kpi-strip" style={{ marginBottom: 8 }}>
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="kpi-card" style={{ opacity: 0.3 }}>
            <div className="kpi-label">…</div><div className="kpi-value">—</div>
          </div>
        ))}
      </div>
    </div>
  )

  const hasRciData = stats?.rci_red_count != null

  return (
    <div>
      {/* ── Row 1: RCI condition bands (UKPMS correct: from red/amber length presence) ── */}
      {hasRciData && (
        <div style={{ marginBottom: 6 }}>
          <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 5 }}>
            RCI Condition Bands — % of sections containing red / amber lengths
          </div>
          <div className="kpi-strip" style={{ marginBottom: 0 }}>
            <KPI
              label="Red Sections"
              value={fmt(stats?.rci_red_count)}
              sub={pct(stats?.rci_red_pct)}
              variant="critical"
            />
            <KPI
              label="Red Lane-km"
              value={km(stats?.total_red_km)}
              sub={stats?.red_network_pct != null ? `${stats.red_network_pct.toFixed(1)}% of network` : null}
            />
            <KPI
              label="Amber Sections"
              value={fmt(stats?.rci_amber_count)}
              sub={pct(stats?.rci_amber_pct)}
              variant="medium"
            />
            <KPI
              label="Amber Lane-km"
              value={km(stats?.total_amber_km)}
              sub={stats?.amber_network_pct != null ? `${stats.amber_network_pct.toFixed(1)}% of network` : null}
            />
            <KPI
              label="Green Sections"
              value={fmt(stats?.rci_green_count)}
              sub={pct(stats?.rci_green_pct)}
              variant="low"
            />
            <KPI
              label="Network Avg CI"
              value={stats?.avg_ci ?? '—'}
              sub="higher = worse"
            />
          </div>
        </div>
      )}

      {/* ── Divider ── */}
      {hasRciData && (
        <div style={{ borderTop: '1px solid var(--border)', margin: '10px 0 6px', position: 'relative' }}>
          <span style={{ position: 'absolute', top: -8, left: 0, fontSize: 10.5, fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--muted)', background: 'var(--bg)', paddingRight: 8 }}>
            Composite Risk Score
          </span>
        </div>
      )}

      {/* ── Row 2: Composite risk bands + totals ── */}
      <div className="kpi-strip">
        <KPI label="Total Assets" value={fmt(stats?.total_assets)} />
        <KPI label="SCANNER"      value={fmt(stats?.scanner_count)} />
        <KPI label="CVI"          value={fmt(stats?.cvi_count)} />
        <KPI label="Critical"     value={fmt(stats?.critical_count)} variant="critical" />
        <KPI label="High Risk"    value={fmt(stats?.high_count)}     variant="high" />
        <KPI label="Medium Risk"  value={fmt(stats?.medium_count)}   variant="medium" />
        {!hasRciData && <KPI label="Network Avg CI" value={stats?.avg_ci ?? '—'} />}
      </div>
    </div>
  )
}
