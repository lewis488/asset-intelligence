import { useEffect, useRef, useState } from 'react'
import { analysisApi, assetsApi } from '../api/client'
import AssetDetailPanel from '../components/AssetDetailPanel'
import PriorityList from '../components/PriorityList'

// ── Hero card: Network Health ─────────────────────────────────────────────────

function NetworkHealthCard({ stats, networkData }) {
  const redPct   = stats?.red_network_pct   ?? 0
  const amberPct = stats?.amber_network_pct ?? 0
  const greenPct = Math.max(0, 100 - redPct - amberPct - ((networkData?.nsgs_with_no_data / (networkData?.total_nsgs || 1)) * 100))
  const unknownPct = Math.max(0, 100 - redPct - amberPct - greenPct)

  const barRef = useRef(null)
  const [animated, setAnimated] = useState(false)
  useEffect(() => {
    if (stats && !animated) {
      const t = setTimeout(() => setAnimated(true), 80)
      return () => clearTimeout(t)
    }
  }, [stats])

  return (
    <div className="card" style={{ position: 'relative', overflow: 'hidden' }}>
      <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-text-muted)', marginBottom: 16 }}>
        Network Condition
      </div>

      <div style={{ display: 'flex', gap: 28, marginBottom: 20 }}>
        <div>
          <div style={{ fontFamily: 'var(--font-data)', fontSize: 32, fontWeight: 700, color: 'var(--color-critical)', lineHeight: 1 }}>
            {redPct.toFixed(2)}%
          </div>
          <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 5 }}>red · of classified network</div>
        </div>
        <div>
          <div style={{ fontFamily: 'var(--font-data)', fontSize: 32, fontWeight: 700, color: 'var(--color-medium)', lineHeight: 1 }}>
            {amberPct.toFixed(2)}%
          </div>
          <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 5 }}>amber · intervention needed</div>
        </div>
      </div>

      {/* Network proportion bar */}
      <div style={{ position: 'relative' }}>
        {/* Amber glow — the one decorative moment */}
        <div style={{
          position: 'absolute', inset: '-8px -12px',
          background: 'radial-gradient(ellipse at 20% 50%, rgba(245,166,35,0.06) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
        <div style={{ height: 8, borderRadius: 99, background: 'rgba(255,255,255,0.06)', overflow: 'hidden', display: 'flex' }}>
          {[
            { pct: redPct,     colour: 'var(--color-critical)' },
            { pct: amberPct,   colour: 'var(--color-medium)' },
            { pct: greenPct,   colour: 'var(--color-low)' },
            { pct: unknownPct, colour: 'rgba(107,114,128,0.4)' },
          ].map(({ pct, colour }, i) => (
            <div key={i} style={{
              width: animated ? `${pct}%` : '0%',
              background: colour,
              transition: `width 600ms ease-out ${i * 80}ms`,
              minWidth: pct > 0.3 ? 2 : 0,
            }} />
          ))}
        </div>
        <div style={{ display: 'flex', gap: 14, marginTop: 8, flexWrap: 'wrap' }}>
          {[
            { label: 'Red',     colour: 'var(--color-critical)', pct: redPct },
            { label: 'Amber',   colour: 'var(--color-medium)',   pct: amberPct },
            { label: 'Green',   colour: 'var(--color-low)',      pct: greenPct },
            { label: 'Unknown', colour: 'var(--color-text-dim)', pct: unknownPct },
          ].map(({ label, colour, pct }) => (
            <span key={label} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--color-text-muted)' }}>
              <span style={{ width: 8, height: 8, borderRadius: 99, background: colour, display: 'inline-block', flexShrink: 0 }} />
              {label} {pct.toFixed(1)}%
            </span>
          ))}
        </div>
      </div>

      {networkData && (
        <div style={{ marginTop: 16, fontSize: 11, color: 'var(--color-text-dim)', fontFamily: 'var(--font-data)' }}>
          {networkData.total_nsgs?.toLocaleString()} NSGs · {networkData.total_length_km?.toLocaleString()}km total
        </div>
      )}
    </div>
  )
}

// ── Hero card: Risk Breakdown ─────────────────────────────────────────────────

const RISK_ROWS = [
  { key: 'critical_count', label: 'Critical', colour: 'var(--color-critical)', band: 'Critical' },
  { key: 'high_count',     label: 'High',     colour: 'var(--color-high)',     band: 'High' },
  { key: 'medium_count',   label: 'Medium',   colour: 'var(--color-medium)',   band: 'Medium' },
  { key: 'low_count',      label: 'Low',      colour: 'var(--color-low)',      band: 'Low' },
]

function RiskBreakdownCard({ stats, bandFilter, onFilterChange }) {
  const total = stats?.total_assets || 1
  const [animated, setAnimated] = useState(false)
  useEffect(() => {
    if (stats && !animated) {
      const t = setTimeout(() => setAnimated(true), 80)
      return () => clearTimeout(t)
    }
  }, [stats])

  return (
    <div className="card">
      <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-text-muted)', marginBottom: 16 }}>
        Risk Breakdown
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {RISK_ROWS.map(({ key, label, colour, band }) => {
          const count = stats?.[key] ?? 0
          const pct = (count / total) * 100
          const isActive = bandFilter === band
          return (
            <div
              key={key}
              onClick={() => onFilterChange(isActive ? '' : band)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '8px 10px',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
                background: isActive ? `${colour}14` : 'transparent',
                border: `1px solid ${isActive ? colour + '44' : 'transparent'}`,
                transition: 'background 150ms, border 150ms',
              }}
            >
              <div style={{ width: 4, height: 28, borderRadius: 99, background: colour, flexShrink: 0,
                opacity: animated ? 1 : 0, transition: 'opacity 300ms ease-out' }} />
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: colour }}>{label}</span>
                  <span style={{ fontFamily: 'var(--font-data)', fontSize: 14, fontWeight: 700, color: 'var(--color-text)' }}>
                    {(count || 0).toLocaleString()}
                  </span>
                </div>
                <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 99, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%', borderRadius: 99, background: colour,
                    width: animated ? `${pct}%` : '0%',
                    transition: 'width 600ms ease-out',
                  }} />
                </div>
              </div>
              <span style={{ fontSize: 11, color: 'var(--color-text-muted)', width: 36, textAlign: 'right', fontFamily: 'var(--font-data)' }}>
                {pct.toFixed(0)}%
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Hero card: Dataset Coverage ───────────────────────────────────────────────

const DATASET_ROWS = [
  { key: 'nsgs_with_scanner',  label: 'SCANNER'  },
  { key: 'nsgs_with_cvi',      label: 'CVI'      },
  { key: 'nsgs_with_scrim',    label: 'SCRIM'    },
  { key: 'nsgs_with_reactive', label: 'Reactive' },
]

function DatasetCoverageCard({ networkData }) {
  const total = networkData?.total_nsgs || 1
  const [animated, setAnimated] = useState(false)
  useEffect(() => {
    if (networkData && !animated) {
      const t = setTimeout(() => setAnimated(true), 80)
      return () => clearTimeout(t)
    }
  }, [networkData])

  return (
    <div className="card">
      <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-text-muted)', marginBottom: 16 }}>
        Dataset Coverage
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {DATASET_ROWS.map(({ key, label }) => {
          const count = networkData?.[key] ?? 0
          const pct = (count / total) * 100
          return (
            <div key={key}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 5 }}>
                <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--color-text)' }}>{label}</span>
                <span style={{ fontSize: 11, color: 'var(--color-text-muted)', fontFamily: 'var(--font-data)' }}>
                  {count.toLocaleString()} / {total.toLocaleString()}
                </span>
              </div>
              <div style={{ height: 5, background: 'rgba(255,255,255,0.06)', borderRadius: 99, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: 99,
                  background: 'var(--color-amber)',
                  width: animated ? `${pct}%` : '0%',
                  transition: 'width 600ms ease-out',
                }} />
              </div>
            </div>
          )
        })}
      </div>
      {networkData && (
        <div style={{ marginTop: 14, fontSize: 11, color: 'var(--color-text-dim)' }}>
          {networkData.by_class && Object.entries(networkData.by_class).map(([cls, km]) => (
            <span key={cls} style={{ marginRight: 10 }}>{cls}: {km}km</span>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Filter bar ────────────────────────────────────────────────────────────────

const BAND_CHIPS = [
  { value: '',         label: 'All' },
  { value: 'Critical', label: 'Critical', variant: 'critical' },
  { value: 'High',     label: 'High',     variant: 'high' },
  { value: 'Medium',   label: 'Medium',   variant: 'medium' },
  { value: 'Low',      label: 'Low',      variant: 'low' },
]

const CLASS_CHIPS = [
  { value: '', label: 'All classes' },
  { value: 'A', label: 'A' },
  { value: 'B', label: 'B' },
  { value: 'C', label: 'C' },
  { value: 'D', label: 'D' },
]

function FilterBar({ bandFilter, onBandFilter, classFilter, onClassFilter, search, onSearch }) {
  return (
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 16, paddingBottom: 14, borderBottom: '1px solid var(--color-border)' }}>
      {/* Band chips */}
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
        {BAND_CHIPS.map(({ value, label, variant }) => (
          <button
            key={value}
            onClick={() => onBandFilter(value)}
            className={`filter-chip${variant ? ` filter-chip--${variant}` : ''}${bandFilter === value ? ' filter-chip--active' : ''}`}
          >
            {label}
          </button>
        ))}
      </div>

      <div style={{ width: 1, height: 20, background: 'var(--color-border)', flexShrink: 0 }} />

      {/* Class chips */}
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
        {CLASS_CHIPS.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => onClassFilter(value)}
            className={`filter-chip${classFilter === value ? ' filter-chip--active' : ''}`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Search */}
      <input
        type="search"
        placeholder="Search by road name or NSG…"
        value={search}
        onChange={e => onSearch(e.target.value)}
        style={{
          marginLeft: 'auto',
          padding: '5px 12px',
          borderRadius: 99,
          border: '1px solid var(--color-border)',
          background: 'var(--color-surface)',
          color: 'var(--color-text)',
          fontSize: 12,
          fontFamily: 'var(--font-ui)',
          outline: 'none',
          width: 220,
        }}
        onFocus={e => e.target.style.borderColor = 'var(--color-blue)'}
        onBlur={e => e.target.style.borderColor = 'var(--color-border)'}
      />
    </div>
  )
}

// ── Dashboard page ────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [stats, setStats]             = useState(null)
  const [assets, setAssets]           = useState([])
  const [total, setTotal]             = useState(0)
  const [page, setPage]               = useState(0)
  const [bandFilter, setBandFilter]   = useState('')
  const [classFilter, setClassFilter] = useState('')
  const [search, setSearch]           = useState('')
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState('')
  const [selectedAsset, setSelectedAsset] = useState(null)
  const [networkData, setNetworkData] = useState(null)

  const limit = 50

  useEffect(() => {
    setLoading(true); setError('')
    Promise.all([
      analysisApi.stats(),
      assetsApi.list({ skip: page * limit, limit, risk_band: bandFilter || undefined }),
      assetsApi.networkStats().catch(() => ({ data: null })),
    ])
      .then(([statsRes, assetsRes, netRes]) => {
        setStats(statsRes.data)
        setAssets(assetsRes.data.assets)
        setTotal(assetsRes.data.total)
        setNetworkData(netRes.data)
      })
      .catch(err => setError(err.response?.data?.detail || 'Failed to load dashboard data'))
      .finally(() => setLoading(false))
  }, [page, bandFilter])

  // Client-side filters (class + search) applied within loaded page
  const filteredAssets = assets.filter(a => {
    if (classFilter && a.road_class !== classFilter) return false
    if (search) {
      const q = search.toLowerCase()
      if (!(a.road_name?.toLowerCase().includes(q) || a.nsg_ref?.toLowerCase().includes(q))) return false
    }
    return true
  })

  const handleRowClick = (asset) =>
    setSelectedAsset(prev => prev?.nsg_ref === asset.nsg_ref ? null : asset)

  const handleBandFilter = (band) => { setBandFilter(band); setPage(0); setSelectedAsset(null) }

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Network risk overview · click any row for full asset intelligence</p>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Hero row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr 1fr', gap: 16, marginBottom: 24 }}>
        <NetworkHealthCard stats={stats} networkData={networkData} />
        <RiskBreakdownCard stats={stats} bandFilter={bandFilter} onFilterChange={handleBandFilter} />
        <DatasetCoverageCard networkData={networkData} />
      </div>

      {/* Priority list */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600 }}>Priority Asset List</h2>
          <span style={{ fontSize: 12, color: 'var(--color-text-muted)', fontFamily: 'var(--font-data)' }}>
            {total.toLocaleString()} assets
          </span>
        </div>

        <FilterBar
          bandFilter={bandFilter}  onBandFilter={handleBandFilter}
          classFilter={classFilter} onClassFilter={v => { setClassFilter(v); setSelectedAsset(null) }}
          search={search}           onSearch={setSearch}
        />

        <PriorityList
          assets={filteredAssets}
          loading={loading}
          onRowClick={handleRowClick}
          selectedNsgRef={selectedAsset?.nsg_ref}
        />

        {total > limit && (
          <div className="pagination">
            <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>← Prev</button>
            <span className="pg-info">Page {page + 1} of {Math.ceil(total / limit)}</span>
            <button onClick={() => setPage(p => p + 1)} disabled={(page + 1) * limit >= total}>Next →</button>
          </div>
        )}
      </div>

      {selectedAsset && (
        <AssetDetailPanel asset={selectedAsset} onClose={() => setSelectedAsset(null)} />
      )}
    </div>
  )
}
