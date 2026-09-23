import { useEffect, useState } from 'react'
import { analysisApi } from '../api/client'

// ── Skeleton loading placeholder ──────────────────────────────────────────────
const Skeleton = ({ lines = [100, 88, 94, 75, 83, 60] }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 4 }}>
    {lines.map((w, i) => (
      <div key={i} style={{
        height: 11, width: `${w}%`, borderRadius: 4,
        background: 'var(--color-border-soft)',
        animation: `pulse 1.6s ease-in-out ${i * 120}ms infinite`,
      }} />
    ))}
  </div>
)

// ── Collapsible section ───────────────────────────────────────────────────────
const Section = ({ title, children, defaultOpen = true }) => {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="detail-section">
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          background: 'none', border: 'none', cursor: 'pointer', padding: 0,
          marginBottom: open ? 10 : 0,
        }}
      >
        <span style={{
          fontSize: 9.5, fontWeight: 500, textTransform: 'uppercase',
          letterSpacing: '0.05em', color: 'var(--color-text-muted)',
        }}>{title}</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
          style={{ color: 'var(--color-text-muted)', flexShrink: 0,
            transform: open ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 150ms' }}>
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </button>
      {open && children}
    </div>
  )
}

// ── Data row ──────────────────────────────────────────────────────────────────
const Row = ({ label, value }) => (
  <div className="detail-row">
    <span className="detail-label">{label}</span>
    <span className="detail-value">{value ?? '—'}</span>
  </div>
)

// ── Helpers ───────────────────────────────────────────────────────────────────
const pct = (v) => v != null ? `${Number(v).toFixed(1)}%` : '—'
const dec = (v, d = 1) => v != null ? Number(v).toFixed(d) : '—'
const num = (v) => v != null ? Number(v).toLocaleString() : '—'

// ── Urgency badge ─────────────────────────────────────────────────────────────
const UrgencyBadge = ({ value }) => {
  if (!value) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  let bg, color
  if (value === 'Immediate') {
    bg = 'var(--color-red-bg)';   color = 'var(--color-red-text)'
  } else if (value === 'This financial year') {
    bg = 'var(--color-amber-bg)'; color = 'var(--color-amber-text)'
  } else if (value.startsWith('Programme')) {
    bg = 'var(--color-amber-bg)'; color = 'var(--color-amber-text)'
  } else if (value.startsWith('Monitor') || value === 'Routine inspection') {
    bg = 'var(--color-green-bg)'; color = 'var(--color-green-text)'
  } else {
    bg = 'var(--color-border-soft)'; color = 'var(--color-text-muted)'
  }
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 10,
      fontSize: 9, fontWeight: 500, background: bg, color,
      textTransform: 'uppercase', letterSpacing: '0.03em',
    }}>
      {value}
    </span>
  )
}

// ── Flag cell ─────────────────────────────────────────────────────────────────
const FlagCell = ({ value, flagged }) => (
  <span>
    {dec(value)}{' '}
    <span style={{ fontSize: 11, fontWeight: 700, color: flagged ? 'var(--color-critical)' : 'var(--color-low)' }}>
      {flagged ? '▲ flagged' : '✓ ok'}
    </span>
  </span>
)

// ── Panel ─────────────────────────────────────────────────────────────────────
export default function AssetDetailPanel({ asset, onClose }) {
  const [narrative, setNarrative]               = useState(null)
  const [narrativeLoading, setNarrativeLoading] = useState(false)
  const [narrativeError, setNarrativeError]     = useState('')

  useEffect(() => {
    if (!asset) return
    setNarrative(null)
    setNarrativeError('')
    setNarrativeLoading(true)
    analysisApi.assetNarrative(asset.nsg_ref)
      .then(r  => setNarrative(r.data))
      .catch(e => setNarrativeError(e.response?.data?.detail || 'Narrative generation failed'))
      .finally(() => setNarrativeLoading(false))
  }, [asset?.nsg_ref])

  if (!asset) return null

  const sd  = asset.scanner_data
  const cd  = asset.cvi_data
  const scr = asset.scrim_data
  const rd  = asset.reactive_data

  const datasetsUsed = [
    asset.has_scanner  && 'SCANNER',
    asset.has_cvi      && 'CVI',
    asset.has_scrim    && 'SCRIM',
    asset.has_reactive && 'Reactive',
  ].filter(Boolean)

  return (
    <div
      className="detail-overlay"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="detail-panel">

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2 style={{ fontSize: 16, fontWeight: 500, margin: 0, lineHeight: 1.3, color: 'var(--color-text)' }}>
              {asset.road_name || 'Unknown Road'}
            </h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
              <code style={{
                fontFamily: 'var(--font-data)', fontSize: 11,
                background: 'var(--color-border-soft)', color: 'var(--color-text-muted)',
                padding: '2px 6px', borderRadius: 4,
              }}>
                {asset.nsg_ref}
              </code>
              {asset.road_class && <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>· {asset.road_class}</span>}
              {asset.parish     && <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>· {asset.parish}</span>}
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              flexShrink: 0, width: 30, height: 30, display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'none', border: '1px solid var(--color-border)', borderRadius: 6,
              cursor: 'pointer', fontSize: 15, color: 'var(--color-text-muted)',
            }}
          >✕</button>
        </div>

        {/* Score summary */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className={`badge badge-${asset.risk_band}`}>{asset.risk_band}</span>
          <span style={{ fontFamily: 'var(--font-data)', fontSize: 22, fontWeight: 500, color: 'var(--color-text)' }}>
            {dec(asset.composite_score)}
          </span>
          <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
            {datasetsUsed.length} / 4 datasets · {asset.score_completeness}% complete
          </span>
        </div>

        {/* Score breakdown chips */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {[
            { label: 'SCANNER', val: asset.scanner_score,  active: asset.has_scanner },
            { label: 'CVI',     val: asset.cvi_score,      active: asset.has_cvi },
            { label: 'SCRIM',   val: asset.scrim_score,    active: asset.has_scrim },
            { label: 'Reactive',val: asset.reactive_score, active: asset.has_reactive },
          ].map(({ label, val, active }) => (
            <span key={label} style={{
              fontSize: 10, padding: '2px 8px', borderRadius: 10, fontWeight: 500,
              background: active ? 'var(--color-accent-soft)' : 'var(--color-border-soft)',
              color:      active ? 'var(--color-accent)'      : 'var(--color-text-muted)',
            }}>
              {label} {dec(val, 0)}
            </span>
          ))}
        </div>

        {/* SCANNER */}
        {asset.has_scanner && sd && (
          <Section title="SCANNER Condition Survey">
            <Row label="Survey year"   value={sd.survey_year} />
            <Row label="Average CI"    value={dec(sd.avg_ci)} />
            <Row label="RCI band"      value={<span className={`badge badge-${sd.rci_band}`}>{sd.rci_band}</span>} />
            <Row label="Red lengths"   value={pct(sd.red_pct)} />
            <Row label="Amber lengths" value={pct(sd.amber_pct)} />
            <p style={{ fontSize: 11, color: 'var(--color-text-dim)', marginTop: 10, fontStyle: 'italic', lineHeight: 1.5 }}>
              Defect driver breakdown available once SCANNER channel data is loaded.
            </p>
          </Section>
        )}

        {/* CVI */}
        {asset.has_cvi && cd && (
          <Section title="CVI Assessment">
            <Row label="Survey year" value={cd.survey_year} />
            <Row label="Structural CI (IL≥85)"
              value={<FlagCell value={cd.max_ci_structural} flagged={cd.structural_flagged} />} />
            <Row label="Edge CI (IL≥50)"
              value={<FlagCell value={cd.max_ci_edge} flagged={cd.edge_flagged} />} />
            <Row label="Wearing Course CI (IL≥60)"
              value={<FlagCell value={cd.max_ci_wearingcourse} flagged={cd.wearingcourse_flagged} />} />
            <Row label="Any domain flagged" value={
              <span style={{ color: cd.any_flagged ? 'var(--color-critical)' : 'var(--color-low)', fontWeight: 700 }}>
                {cd.any_flagged ? 'Yes' : 'No'}
              </span>
            } />
          </Section>
        )}

        {/* SCRIM */}
        {asset.has_scrim && scr && (
          <Section title="SCRIM Skid Resistance">
            <Row label="Survey year"           value={scr.survey_year} />
            <Row label="Mean SFC"              value={dec(scr.mean_sfc, 3)} />
            <Row label="Investigatory level"   value={dec(scr.sfct_threshold, 3)} />
            <Row label="Status" value={
              <span style={{ fontWeight: 700, color: scr.safety_flagged ? 'var(--color-critical)' : 'var(--color-low)' }}>
                {scr.safety_flagged ? '▲ Below IL — safety risk' : '✓ Above IL'}
              </span>
            } />
            <Row label="Worst XDIF (margin)"   value={dec(scr.worst_xdif, 3)} />
            <Row label="% of section below IL" value={pct(scr.pct_below_il)} />
          </Section>
        )}

        {/* REACTIVE */}
        {asset.has_reactive && rd && (
          <Section title="Reactive Maintenance">
            <Row label="Year"                    value={rd.year} />
            <Row label="Total jobs raised"       value={num(rd.total_jobs_raised)} />
            <Row label="Potholes"                value={num(rd.pothole_count)} />
            <Row label="Edge repairs"            value={num(rd.edge_count)} />
            <Row label="Emergency (Cat 1, 2hr)"  value={num(rd.emergency_jobs_2hr)} />
            <Row label="Urgent (Cat 2, 24hr)"    value={num(rd.urgent_jobs_24hr)} />
            <Row label="Days since last defect"  value={num(rd.days_since_most_recent_defect)} />
            <Row label="Mean days to completion" value={dec(rd.mean_days_to_completion)} />
          </Section>
        )}

        {/* TREATMENT */}
        <Section title="Indicative treatment candidate">
          <div style={{ fontWeight: 500, fontSize: 14, marginBottom: 12, lineHeight: 1.4, color: 'var(--color-text)' }}>
            {asset.treatment_recommendation || 'Not assessed'}
          </div>
          <Row label="Screening priority" value={<UrgencyBadge value={asset.urgency} />} />
          {(asset.cost_low_per_m2 > 0 || asset.cost_high_per_m2 > 0) && (
            <Row label="Indicative cost" value={`£${asset.cost_low_per_m2}–${asset.cost_high_per_m2} per m²`} />
          )}
          <Row label="Dataset availability" value={asset.confidence || '—'} />
          <p style={{ fontSize: 12, color: 'var(--color-text-dim)', lineHeight: 1.5 }}>
            Engineering review must confirm the failure mechanism and treatment suitability.
            Dataset availability is not diagnostic confidence; screening priorities are not approved works deadlines.
          </p>
          {datasetsUsed.length > 0 && (
            <div style={{ marginTop: 10, fontSize: 12, color: 'var(--color-text-dim)' }}>
              Based on: {datasetsUsed.join(', ')}
            </div>
          )}
        </Section>

        {/* AI ASSESSMENT */}
        <Section title="AI Assessment">
          {narrativeLoading && <Skeleton />}
          {narrativeError && !narrativeLoading && (
            <div className="alert alert-error">{narrativeError}</div>
          )}
          {narrative && !narrativeLoading && (
            <>
              <div className="briefing-body">{narrative.narrative}</div>
              <div style={{ marginTop: 10, fontSize: 11, color: 'var(--color-text-dim)' }}>
                {narrative.cached ? 'Cached · ' : ''}
                Data: {narrative.data_used?.join(', ')} ·{' '}
                {new Date(narrative.generated_at).toLocaleString()}
              </div>
            </>
          )}
        </Section>

      </div>
    </div>
  )
}
