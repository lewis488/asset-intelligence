import { useEffect, useState } from 'react'
import { analysisApi } from '../api/client'

// ── Primitives ────────────────────────────────────────────────────────────────

const Section = ({ title, children }) => (
  <div className="detail-section">
    <div className="detail-section-title">{title}</div>
    {children}
  </div>
)

const Row = ({ label, value }) => (
  <div className="detail-row">
    <span className="detail-label">{label}</span>
    <span className="detail-value">{value ?? '—'}</span>
  </div>
)

// ── Helpers ───────────────────────────────────────────────────────────────────

const dec = (v, d = 2) => v != null ? Number(v).toFixed(d) : '—'
const pct = (v) => v != null ? `${(Number(v) * 100).toFixed(0)}%` : '—'   // 0–1 fractions
const pct100 = (v) => v != null ? `${Number(v).toFixed(1)}%` : '—'        // 0–100 whole-%

const RAG_COLOUR = { Red: '#c0432f', Amber: '#d9a51c', Green: '#3a7d44' }

// ── Severity tier constants (must match backend DEFECT_SEVERITY_TIERS) ────────

const TIER_ORDER = ['Structural', 'High', 'Medium', 'Low']

const TIER_DEFECTS = {
  Structural: [
    'Subsidence', 'Severe pothole', 'Alligator cracking',
    'Wheel track cracking', 'Severe longitudinal cracking', 'Severe transverse cracking',
  ],
  High: ['Moderate pothole', 'Binder bleeding'],
  Medium: ['Minor pothole', 'Severe fretting', 'Defective asphalt overlay'],
  Low: [
    'Left edge deterioration', 'Right edge deterioration',
    'Moderate longitudinal cracking', 'Moderate transverse cracking',
    'Moderate fretting', 'Minor longitudinal cracking', 'Minor transverse cracking',
  ],
}

const TIER_COLOUR = {
  Structural: 'var(--color-red)',
  High:       'var(--color-amber)',
  Medium:     '#5B82B8',
  Low:        'var(--color-green)',
}

// ── Sub-components ────────────────────────────────────────────────────────────

function RagBadge({ band }) {
  if (!band) return <span style={{ color: 'var(--muted)' }}>—</span>
  const colour = RAG_COLOUR[band] || '#888'
  return (
    <span style={{
      display: 'inline-block', padding: '2px 10px', borderRadius: 99,
      fontSize: 12, fontWeight: 700,
      background: colour + '22', color: colour,
      border: `1px solid ${colour}44`,
    }}>{band}</span>
  )
}

function TierRow({ tier, tierPct, defectProportions, expanded, onToggle }) {
  const colour = TIER_COLOUR[tier] || '#888'
  const present = (TIER_DEFECTS[tier] || [])
    .map(k => ({ name: k, value: defectProportions?.[k] ?? 0 }))
    .filter(d => d.value > 0)
    .sort((a, b) => b.value - a.value)
  const hasPct = tierPct != null && tierPct > 0

  return (
    <div style={{
      border: '1px solid var(--color-border)',
      borderRadius: 'var(--radius-sm)',
      overflow: 'hidden',
      marginBottom: 6,
    }}>
      <button
        onClick={() => present.length > 0 && onToggle()}
        style={{
          width: '100%', background: 'none', border: 'none',
          cursor: present.length > 0 ? 'pointer' : 'default',
          padding: '8px 10px', display: 'flex', alignItems: 'center', gap: 8,
          textAlign: 'left', fontFamily: 'var(--font-ui)',
        }}
      >
        <span style={{
          fontSize: 12, fontWeight: 700, letterSpacing: '0.03em',
          color: hasPct ? colour : 'var(--color-text-muted)',
          minWidth: 72,
        }}>{tier.toUpperCase()}</span>
        <span style={{ flex: 1 }} />
        <span style={{
          fontSize: 13, fontWeight: 700,
          color: hasPct ? 'var(--color-text)' : 'var(--color-text-muted)',
        }}>
          {hasPct ? `${Number(tierPct).toFixed(1)}%` : '—'}
        </span>
        {present.length > 0 && (
          <span style={{ fontSize: 10, color: 'var(--color-text-muted)', marginLeft: 4 }}>
            {expanded ? '▲' : '▼'}
          </span>
        )}
      </button>

      {hasPct && (
        <div style={{ height: 3, background: 'var(--color-border-soft)' }}>
          <div style={{
            height: '100%', background: colour,
            width: `${Math.min(100, tierPct)}%`,
          }} />
        </div>
      )}

      {expanded && present.length > 0 && (
        <div style={{
          padding: '6px 10px 8px',
          borderTop: '1px solid var(--color-border-soft)',
          background: 'var(--color-border-soft)',
        }}>
          {present.map(d => (
            <div key={d.name} style={{
              display: 'flex', justifyContent: 'space-between',
              fontSize: 12, padding: '3px 0',
            }}>
              <span style={{ color: 'var(--color-text-muted)' }}>{d.name}</span>
              <span style={{ fontWeight: 600 }}>{Number(d.value).toFixed(1)}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function TreatmentSuitabilityBar({ label, value, colour }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        fontSize: 13, marginBottom: 4,
      }}>
        <span>{label}</span>
        <span style={{ fontWeight: 600 }}>
          {value != null && value > 0 ? `${Number(value).toFixed(1)}%` : '—'}
        </span>
      </div>
      <div style={{ height: 6, background: 'var(--color-border)', borderRadius: 3 }}>
        <div style={{
          height: '100%', borderRadius: 3, background: colour,
          width: `${Math.min(100, value || 0)}%`,
        }} />
      </div>
    </div>
  )
}

// ── Panel ─────────────────────────────────────────────────────────────────────

export default function VaisalaSectionDetailPanel({ section, surveyMeta, onClose }) {
  const [narrative, setNarrative] = useState(null)
  const [narrativeLoading, setNarrativeLoading] = useState(false)
  const [narrativeError, setNarrativeError] = useState('')
  const [expandedTiers, setExpandedTiers] = useState({})

  useEffect(() => {
    if (!section) return
    setNarrative(null)
    setNarrativeError('')
    setNarrativeLoading(true)
    setExpandedTiers({})
    analysisApi.vaisalaSectionNarrative(section.id)
      .then(r => setNarrative(r.data))
      .catch(e => setNarrativeError(e.response?.data?.detail || 'Narrative generation failed'))
      .finally(() => setNarrativeLoading(false))
  }, [section?.id])

  if (!section) return null

  const hasNativeScores = section.road_surface_condition != null
    || section.asphalt_condition != null
    || section.pas2161_category != null
  const hasQC = section.qc_completeness_band != null || section.qc_reliability_band != null
  const hasSeverityTiers = section.severity_tier_pcts != null
  const hasTreatmentSuitability = section.dressing_pct != null || section.micro_pct != null

  const ragColour = RAG_COLOUR[section.rag_band] || '#888'
  const lowQC = section.qc_completeness_band === 'Low' || section.qc_reliability_band === 'Low'

  const toggleTier = (tier) =>
    setExpandedTiers(prev => ({ ...prev, [tier]: !prev[tier] }))

  return (
    <div
      className="detail-overlay"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="detail-panel">

        {/* ── Header ─────────────────────────────────────────────────── */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, lineHeight: 1.3 }}>
              {section.road_name || 'Unknown Road'}
            </h2>
            <div style={{ color: 'var(--muted)', fontSize: 12, marginTop: 4, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <code style={{ fontFamily: 'monospace', background: '#f1f5f9', padding: '1px 5px', borderRadius: 3 }}>
                {section.section_ref}
              </code>
              {section.road_class && <span>· {section.road_class}</span>}
              {section.urban_rural && <span>· {section.urban_rural}</span>}
              {surveyMeta?.network_key && <span>· {surveyMeta.network_key}</span>}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ flexShrink: 0, background: 'none', border: '1px solid var(--border)', borderRadius: 6, width: 30, height: 30, cursor: 'pointer', fontSize: 15, color: 'var(--muted)', lineHeight: 1 }}
            aria-label="Close"
          >✕</button>
        </div>

        {/* ── Score + RAG summary ─────────────────────────────────── */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <RagBadge band={section.rag_band} />
          <span style={{ fontSize: 22, fontWeight: 800 }}>{dec(section.priority_score)}</span>
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>
            List 4 weighted score · {dec(section.length_m, 0)}m
          </span>
        </div>

        {/* Drift warning */}
        {surveyMeta?.has_weight_drift && (
          <div style={{ fontSize: 12, color: '#d9a51c', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 6, padding: '8px 12px' }}>
            <strong>RAG weight drift.</strong> Defect weights used for this survey differ from the validated set.
            The Red/Amber thresholds (4.0 / 1.8) are not reliable for this section — treat RAG banding as indicative.
          </div>
        )}

        {/* Low QC warning */}
        {hasQC && lowQC && (
          <div style={{ fontSize: 12, color: '#c0432f', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 6, padding: '8px 12px' }}>
            <strong>Low QC signal.</strong> One or more QC metrics are below threshold — score and treatment
            should be treated as provisional pending video validation.
          </div>
        )}

        {/* ── Vaisala DST Score ───────────────────────────────────── */}
        <Section title="Vaisala DST — List 4 Score">
          <Row label="Priority score (weighted)" value={<strong>{dec(section.priority_score)}</strong>} />
          <Row label="Worst interval score" value={dec(section.worst_interval_score)} />
          <Row label="RAG band" value={<RagBadge band={section.rag_band} />} />
          <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 8, fontStyle: 'italic', lineHeight: 1.5 }}>
            Red ≥ 4.0 · Amber ≥ 1.8 · Green &lt; 1.8 — fixed evidence-derived thresholds, not percentile ranks.
          </p>
        </Section>

        {/* ── Treatment ───────────────────────────────────────────── */}
        <Section title="Treatment Recommendation">
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 10 }}>
            {section.treatment || 'Not assessed'}
          </div>
        </Section>

        {/* ── Defect Analysis (primary/secondary only) ────────────── */}
        {section.primary_defect && (
          <Section title="Defect Analysis">
            <Row
              label="Primary defect"
              value={
                <span>
                  <strong>{section.primary_defect}</strong>
                  {section.primary_defect_contribution != null && (
                    <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 6 }}>
                      ({dec(section.primary_defect_contribution, 4)} score units)
                    </span>
                  )}
                </span>
              }
            />
            {section.secondary_defect && (
              <Row
                label="Secondary defect"
                value={
                  <span>
                    {section.secondary_defect}
                    {section.secondary_defect_contribution != null && (
                      <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 6 }}>
                        ({dec(section.secondary_defect_contribution, 4)} score units)
                      </span>
                    )}
                  </span>
                }
              />
            )}
          </Section>
        )}

        {/* ── Panel 1: Defect Severity Breakdown ──────────────────── */}
        {hasSeverityTiers && (
          <Section title="Defect Severity Breakdown">

            {/* Top-line structural indicator — treatment-group metric, MAX-based */}
            {section.structural_pct != null && (
              <div style={{
                background: section.structural_pct > 0
                  ? 'var(--color-red-bg)' : 'var(--color-border-soft)',
                border: `1px solid ${section.structural_pct > 0 ? 'var(--color-red)' : 'var(--color-border)'}33`,
                borderRadius: 'var(--radius-sm)',
                padding: '8px 10px',
                marginBottom: 12,
                fontSize: 13,
              }}>
                <span style={{
                  fontWeight: 700,
                  color: section.structural_pct > 0 ? 'var(--color-red)' : 'var(--color-text-muted)',
                }}>
                  Severe structural defect:{' '}
                  {section.structural_pct > 0 ? `${Number(section.structural_pct).toFixed(1)}% of section` : 'not detected'}
                </span>
                <span style={{ fontSize: 11, color: 'var(--color-text-muted)', display: 'block', marginTop: 3 }}>
                  Coverage flag (MAX-based). Not directly comparable to tier percentages below.
                </span>
              </div>
            )}

            {/* Tier rows — Structural/High/Medium/Low */}
            <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 8 }}>
              % of section length · click tier to expand defects
            </div>
            {TIER_ORDER.map(tier => (
              <TierRow
                key={tier}
                tier={tier}
                tierPct={section.severity_tier_pcts?.[tier]}
                defectProportions={section.defect_proportions}
                expanded={!!expandedTiers[tier]}
                onToggle={() => toggleTier(tier)}
              />
            ))}
          </Section>
        )}

        {/* ── Panel 2: Treatment Suitability ──────────────────────── */}
        {hasTreatmentSuitability && (
          <div className="detail-section" style={{
            borderTop: '2px solid var(--color-border)',
            paddingTop: 14,
          }}>
            <div className="detail-section-title">Treatment Suitability</div>
            <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 12, lineHeight: 1.5 }}>
              How well this section's defect profile matches each candidate treatment.
              Feeds the recommendation above.
            </p>
            <TreatmentSuitabilityBar
              label="Surface Dressing"
              value={section.dressing_pct}
              colour="var(--color-amber)"
            />
            <TreatmentSuitabilityBar
              label="Micro-surfacing"
              value={section.micro_pct}
              colour="#5B82B8"
            />
          </div>
        )}

        {/* ── Native Vaisala scores ────────────────────────────────── */}
        {hasNativeScores && (
          <Section title="Vaisala Native Condition Scores">
            {section.road_surface_condition != null && (
              <Row label="RSC score"
                value={`${dec(section.road_surface_condition)}${section.road_surface_condition_class ? ` (Class ${section.road_surface_condition_class})` : ''}`} />
            )}
            {section.asphalt_condition != null && (
              <Row label="Asphalt condition"
                value={`${dec(section.asphalt_condition)}${section.asphalt_condition_class ? ` (Class ${section.asphalt_condition_class})` : ''}`} />
            )}
            {section.pas2161_category != null && (
              <Row label="PAS 2161 category" value={section.pas2161_category} />
            )}
            <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 8, fontStyle: 'italic', lineHeight: 1.5 }}>
              RSC / Asphalt: lower score = worse condition (Class 1 = worst). PAS 2161: higher category = more severe.
            </p>
          </Section>
        )}

        {/* ── QC ──────────────────────────────────────────────────── */}
        {hasQC && (
          <Section title="Data QC">
            {section.qc_completeness_pct != null && (
              <Row
                label="Survey completeness"
                value={
                  <span>
                    {pct(section.qc_completeness_pct)}
                    {section.qc_completeness_band && (
                      <span style={{ marginLeft: 6, fontSize: 11, fontWeight: 700,
                        color: section.qc_completeness_band === 'Low' ? '#c0432f'
                          : section.qc_completeness_band === 'Medium' ? '#d9a51c' : '#3a7d44' }}>
                        {section.qc_completeness_band}
                      </span>
                    )}
                  </span>
                }
              />
            )}
            {section.qc_reliability_pct != null && (
              <Row
                label="Reading reliability"
                value={
                  <span>
                    {pct(section.qc_reliability_pct)}
                    {section.qc_reliability_band && (
                      <span style={{ marginLeft: 6, fontSize: 11, fontWeight: 700,
                        color: section.qc_reliability_band === 'Low' ? '#c0432f'
                          : section.qc_reliability_band === 'Medium' ? '#d9a51c' : '#3a7d44' }}>
                        {section.qc_reliability_band}
                      </span>
                    )}
                  </span>
                }
              />
            )}
            <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 8, fontStyle: 'italic', lineHeight: 1.5 }}>
              Completeness: how much of the section was physically surveyed. Reliability: of what was surveyed,
              how much Vaisala itself judged valid. These are independent signals.
            </p>
          </Section>
        )}

        {/* ── AI Assessment ───────────────────────────────────────── */}
        <Section title="AI Assessment">
          {narrativeLoading && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, color: 'var(--muted)', fontSize: 13, padding: '4px 0' }}>
              <span className="spinner" /> Generating assessment…
            </div>
          )}
          {narrativeError && !narrativeLoading && (
            <div className="alert alert-error">{narrativeError}</div>
          )}
          {narrative && !narrativeLoading && (
            <>
              <div className="briefing-body">{narrative.narrative}</div>
              <div style={{ marginTop: 10, fontSize: 11, color: 'var(--muted)' }}>
                {narrative.cached ? 'Cached · ' : ''}
                {new Date(narrative.generated_at).toLocaleString()}
              </div>
            </>
          )}
        </Section>

      </div>
    </div>
  )
}
