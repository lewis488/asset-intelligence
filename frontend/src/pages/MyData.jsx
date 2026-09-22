import { useEffect, useState } from 'react'
import { assetsApi } from '../api/client'

// ── Icons (Tabler-style, 20×20) ───────────────────────────────────────────────
const Ic = {
  scanner: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12h3l3-8 3 16 3-8 3 4h3"/>
    </svg>
  ),
  cvi: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
      <circle cx="12" cy="12" r="3"/>
    </svg>
  ),
  scrim: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
    </svg>
  ),
  reactive: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
    </svg>
  ),
  network: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
      <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
    </svg>
  ),
  vaisala: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12.55a11 11 0 0 1 14.08 0"/>
      <path d="M1.42 9a16 16 0 0 1 21.16 0"/>
      <path d="M8.53 16.11a6 6 0 0 1 6.95 0"/>
      <line x1="12" y1="20" x2="12.01" y2="20"/>
    </svg>
  ),
}

const DATASETS = [
  { key: 'scanner',  label: 'Scanner Raw',  sub: 'SCANNER CI survey data',          color: '#3B82F6', icon: Ic.scanner  },
  { key: 'cvi',      label: 'CVI Raw',      sub: 'Condition Visual Inspection',      color: '#FACC15', icon: Ic.cvi      },
  { key: 'scrim',    label: 'SCRIM Raw',    sub: 'Skid resistance measurement',      color: '#F87171', icon: Ic.scrim    },
  { key: 'reactive', label: 'Reactive',     sub: 'Reactive maintenance jobs',        color: '#FB923C', icon: Ic.reactive },
  { key: 'network',  label: 'Network',      sub: 'NSG road network register',        color: '#34D399', icon: Ic.network  },
  { key: 'vaisala',  label: 'Vaisala DST',  sub: 'RoadAI pavement survey',           color: '#F5A623', icon: Ic.vaisala  },
]

function fmt(n) {
  return n == null ? '—' : Number(n).toLocaleString()
}

function fmtDate(iso) {
  if (!iso) return null
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function DatasetCard({ config, data }) {
  const { key, label, sub, color, icon } = config
  const isVaisala = key === 'vaisala'
  const isEmpty = isVaisala ? !(data?.surveys) : !(data?.records)
  const years = data?.survey_years ?? []
  const updated = fmtDate(data?.last_updated)

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', opacity: isEmpty ? 0.45 : 1, transition: 'opacity 200ms' }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 14 }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-muted)' }}>
            {label}
          </div>
          <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginTop: 2 }}>{sub}</div>
        </div>
        <span style={{ color, opacity: isEmpty ? 0.4 : 0.75, flexShrink: 0, marginLeft: 8 }}>{icon}</span>
      </div>

      {/* Primary metric */}
      {isVaisala ? (
        <>
          <div style={{ fontFamily: 'var(--font-data)', fontSize: 26, fontWeight: 700, color: isEmpty ? 'var(--color-text-dim)' : color, lineHeight: 1 }}>
            {isEmpty ? '—' : fmt(data.surveys)}
          </div>
          <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 3, marginBottom: 12 }}>
            {isEmpty ? 'no surveys' : `surveys · ${fmt(data.sections)} sections`}
          </div>
        </>
      ) : (
        <>
          <div style={{ fontFamily: 'var(--font-data)', fontSize: 26, fontWeight: 700, color: isEmpty ? 'var(--color-text-dim)' : color, lineHeight: 1 }}>
            {isEmpty ? '—' : fmt(data.records)}
          </div>
          <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 3, marginBottom: 12 }}>
            {isEmpty ? 'no data uploaded' : 'records'}
          </div>
        </>
      )}

      {/* Year chips */}
      {years.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 12 }}>
          {years.map(y => (
            <span key={y} style={{
              fontSize: 10, fontFamily: 'var(--font-data)', fontWeight: 600,
              padding: '2px 7px', borderRadius: 99,
              background: `${color}18`, color, border: `1px solid ${color}28`,
            }}>{y}</span>
          ))}
        </div>
      )}

      {/* Footer */}
      <div style={{ marginTop: 'auto', fontSize: 11, color: 'var(--color-text-dim)' }}>
        {updated ? `Updated ${updated}` : isEmpty ? '' : ''}
      </div>
    </div>
  )
}

function DatasetGrid({ datasets }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))', gap: 14 }}>
      {DATASETS.map(cfg => (
        <DatasetCard key={cfg.key} config={cfg} data={datasets?.[cfg.key]} />
      ))}
    </div>
  )
}

export default function MyData() {
  const [data, setData]           = useState(null)
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const [selectedId, setSelectedId] = useState(null)

  useEffect(() => {
    assetsApi.myDatasets()
      .then(r => {
        const d = r.data
        setData(d)
        if (d.authorities?.length > 0) setSelectedId(d.authorities[0].authority_id)
      })
      .catch(() => setError('Failed to load dataset inventory'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div style={{ color: 'var(--color-text-dim)', padding: 40, fontFamily: 'var(--font-data)', fontSize: 13 }}>
      Loading…
    </div>
  )

  if (error) return (
    <div className="alert alert-error" style={{ marginTop: 0 }}>{error}</div>
  )

  const isAdmin = !!data?.authorities
  const selectedAuth = isAdmin ? data.authorities.find(a => a.authority_id === selectedId) : null
  const datasets = isAdmin ? selectedAuth?.datasets : data

  return (
    <div>
      <div className="page-header">
        <h1>My Data</h1>
        <p>Dataset inventory — records held for this authority</p>
      </div>

      {isAdmin && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
          <select
            value={selectedId ?? ''}
            onChange={e => setSelectedId(Number(e.target.value))}
            style={{
              background: 'var(--color-panel)',
              border: '1px solid var(--color-border-strong)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--color-text)',
              padding: '7px 12px',
              fontSize: 13,
              fontFamily: 'var(--font-ui)',
              cursor: 'pointer',
              minWidth: 220,
              outline: 'none',
            }}
          >
            {data.authorities.map(a => (
              <option key={a.authority_id} value={a.authority_id}>{a.authority_name}</option>
            ))}
          </select>
          <span style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>
            {data.total_authorities} {data.total_authorities === 1 ? 'authority' : 'authorities'} with data
          </span>
        </div>
      )}

      {datasets ? (
        <DatasetGrid datasets={datasets} />
      ) : (
        <div style={{ color: 'var(--color-text-dim)', fontSize: 13 }}>No data found.</div>
      )}
    </div>
  )
}
