import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import { useEffect, useState } from 'react'
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet'
import { analysisApi, assetsApi } from '../api/client'
import AssetDetailPanel from '../components/AssetDetailPanel'
import PriorityList from '../components/PriorityList'

// ── Risk colours (saturated — map lines) ─────────────────────────────────────
const MAP_COLOURS = {
  Critical: '#C0453A',
  High:     '#D89A3D',
  Medium:   '#D89A3D',
  Low:      '#4A8B6F',
}
const MAP_COLOUR_UNKNOWN = '#94A3B8'

function riskColour(band) { return MAP_COLOURS[band] || MAP_COLOUR_UNKNOWN }

// ── Auto-fit map to GeoJSON bounds ───────────────────────────────────────────
function FitBounds({ geojson }) {
  const map = useMap()
  useEffect(() => {
    if (!geojson?.features?.length) return
    try {
      const layer = L.geoJSON(geojson)
      const bounds = layer.getBounds()
      if (bounds.isValid()) map.fitBounds(bounds, { padding: [16, 16] })
    } catch {}
  }, [geojson, map])
  return null
}

// ── Network map card ──────────────────────────────────────────────────────────
function NetworkMapCard({ geojson, networkData, onFeatureClick }) {
  const geoKey = geojson?.features?.length ?? 0

  const styleFeature = (feature) => ({
    color: riskColour(feature.properties?.risk_band),
    weight: 3,
    opacity: 0.85,
  })

  const onEachFeature = (feature, layer) => {
    layer.on('click', () => onFeatureClick && onFeatureClick(feature.properties?.nsg_ref))
    layer.on('mouseover', (e) => {
      e.target.setStyle({ weight: 5, opacity: 1 })
      layer.bindTooltip(
        `<strong>${feature.properties?.road_name || feature.properties?.nsg_ref}</strong>` +
        `<br/>${feature.properties?.risk_band || 'No score'} · ${feature.properties?.road_class || ''}`,
        { sticky: true }
      ).openTooltip(e.latlng)
    })
    layer.on('mouseout', (e) => {
      e.target.setStyle({ weight: 3, opacity: 0.85 })
    })
  }

  const totalNsgs = networkData?.total_nsgs?.toLocaleString() ?? '—'
  const totalKm   = networkData?.total_length_km?.toLocaleString() ?? '—'

  return (
    <div className="card" style={{ padding: 0, position: 'relative', overflow: 'hidden', height: '100%' }}>
      <MapContainer
        center={[51.5, -0.5]}
        zoom={9}
        style={{ width: '100%', height: '100%', borderRadius: 'var(--radius-md)' }}
        zoomControl={true}
        attributionControl={false}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
          maxZoom={20}
        />
        {geojson && (
          <GeoJSON
            key={geoKey}
            data={geojson}
            style={styleFeature}
            onEachFeature={onEachFeature}
          />
        )}
        {geojson && <FitBounds geojson={geojson} />}
      </MapContainer>

      {/* Title overlay */}
      <div style={{
        position: 'absolute', top: 12, left: 12, zIndex: 500,
        background: 'rgba(255,255,255,0.92)',
        backdropFilter: 'blur(4px)',
        borderRadius: 'var(--radius-sm)',
        padding: '6px 10px',
        border: '0.5px solid var(--color-border)',
        pointerEvents: 'none',
      }}>
        <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--color-text)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Network map
        </div>
        <div style={{ fontSize: 10, color: 'var(--color-text-muted)', marginTop: 1 }}>
          {totalNsgs} sections · {totalKm}km
        </div>
      </div>

      {/* Legend overlay */}
      <div style={{
        position: 'absolute', bottom: 12, left: 12, zIndex: 500,
        background: 'rgba(255,255,255,0.92)',
        backdropFilter: 'blur(4px)',
        borderRadius: 'var(--radius-sm)',
        padding: '6px 10px',
        border: '0.5px solid var(--color-border)',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        pointerEvents: 'none',
      }}>
        {[
          { label: 'Critical', colour: MAP_COLOURS.Critical },
          { label: 'High',     colour: MAP_COLOURS.High },
          { label: 'Low',      colour: MAP_COLOURS.Low },
          { label: 'Unknown',  colour: MAP_COLOUR_UNKNOWN },
        ].map(({ label, colour }) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 16, height: 3, borderRadius: 99, background: colour, flexShrink: 0 }} />
            <span style={{ fontSize: 10, color: 'var(--color-text-muted)' }}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Card 1: Red network hero stat ─────────────────────────────────────────────
function RedNetworkCard({ stats }) {
  const redPct = stats?.red_network_pct ?? null
  return (
    <div className="card">
      <div style={{ fontSize: 9.5, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-muted)', marginBottom: 8 }}>
        Red network
      </div>
      {redPct !== null ? (
        <>
          <div style={{ fontSize: 36, fontWeight: 500, color: 'var(--color-red-text)', lineHeight: 1 }}>
            {redPct.toFixed(2)}%
          </div>
          <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 6 }}>
            of classified network · matches published 5.7%
          </div>
        </>
      ) : (
        <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>No data</div>
      )}
    </div>
  )
}

// ── Card 2: Risk mix (dark panel) ─────────────────────────────────────────────
const RISK_MIX_ROWS = [
  { key: 'critical_count', label: 'Critical', bg: 'rgba(192,69,58,0.6)',  fill: 'rgba(192,69,58,0.85)' },
  { key: 'high_count',     label: 'High',     bg: 'rgba(216,154,61,0.6)', fill: 'rgba(216,154,61,0.85)' },
  { key: 'medium_count',   label: 'Medium',   bg: 'rgba(216,154,61,0.4)', fill: 'rgba(216,154,61,0.7)' },
  { key: 'low_count',      label: 'Low',      bg: 'rgba(74,139,111,0.6)', fill: 'rgba(74,139,111,0.85)' },
]

function RiskMixCard({ stats }) {
  const total = stats?.total_assets || 1
  const [animated, setAnimated] = useState(false)
  useEffect(() => {
    if (stats && !animated) {
      const t = setTimeout(() => setAnimated(true), 80)
      return () => clearTimeout(t)
    }
  }, [stats])

  return (
    <div style={{
      background: 'var(--color-panel-dark)',
      border: '0.5px solid rgba(255,255,255,0.08)',
      borderRadius: 'var(--radius-md)',
      padding: '16px 20px',
    }}>
      <div style={{ fontSize: 9.5, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-on-dark-muted)', marginBottom: 12 }}>
        Risk mix
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {RISK_MIX_ROWS.map(({ key, label, bg, fill }) => {
          const count = stats?.[key] ?? 0
          const pct   = Math.round((count / total) * 100)
          return (
            <div key={key}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                <span style={{ fontSize: 11, color: 'var(--color-text-on-dark-muted)' }}>{label}</span>
                <span style={{ fontSize: 11, color: 'var(--color-text-on-dark)', fontWeight: 500 }}>
                  {count.toLocaleString()}
                </span>
              </div>
              <div style={{ height: 5, background: 'var(--color-panel-dark-2)', borderRadius: 99, overflow: 'hidden' }}>
                <div style={{
                  height: '100%',
                  borderRadius: 99,
                  background: fill,
                  width: animated ? `${pct}%` : '0%',
                  transition: 'width 600ms ease-out',
                }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Card 3: Priority sections preview ─────────────────────────────────────────
function PrioritySectionsCard({ assets, onRowClick, selectedNsgRef }) {
  const top5 = assets.slice(0, 5)
  return (
    <div className="card" style={{ flex: 1 }}>
      <div style={{ fontSize: 9.5, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-muted)', marginBottom: 10 }}>
        Priority sections
      </div>
      {top5.length === 0 ? (
        <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>No assets scored yet</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {top5.map(a => (
            <div
              key={a.nsg_ref}
              onClick={() => onRowClick(a)}
              style={{
                padding: '8px 0',
                borderBottom: '0.5px solid var(--color-border-soft)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 8,
                background: selectedNsgRef === a.nsg_ref ? 'var(--color-accent-soft)' : 'transparent',
                borderRadius: selectedNsgRef === a.nsg_ref ? 'var(--radius-sm)' : 0,
                transition: 'background 120ms',
              }}
              onMouseEnter={e => { if (selectedNsgRef !== a.nsg_ref) e.currentTarget.style.background = 'var(--color-border-soft)' }}
              onMouseLeave={e => { if (selectedNsgRef !== a.nsg_ref) e.currentTarget.style.background = 'transparent' }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--color-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {a.road_name || a.nsg_ref}
                </div>
                <div style={{ fontSize: 10, color: 'var(--color-text-muted)', marginTop: 1 }}>
                  {[a.road_class, a.parish].filter(Boolean).join(' · ')}
                </div>
              </div>
              {a.risk_band && (
                <span className={`badge badge-${a.risk_band}`} style={{ flexShrink: 0 }}>
                  {a.risk_band}
                </span>
              )}
            </div>
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
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 14, paddingBottom: 12, borderBottom: '0.5px solid var(--color-border)' }}>
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
        {BAND_CHIPS.map(({ value, label, variant }) => (
          <button key={value} onClick={() => onBandFilter(value)}
            className={`filter-chip${variant ? ` filter-chip--${variant}` : ''}${bandFilter === value ? ' filter-chip--active' : ''}`}>
            {label}
          </button>
        ))}
      </div>
      <div style={{ width: 1, height: 20, background: 'var(--color-border)', flexShrink: 0 }} />
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
        {CLASS_CHIPS.map(({ value, label }) => (
          <button key={value} onClick={() => onClassFilter(value)}
            className={`filter-chip${classFilter === value ? ' filter-chip--active' : ''}`}>
            {label}
          </button>
        ))}
      </div>
      <input
        type="search"
        placeholder="Search by road name or NSG…"
        value={search}
        onChange={e => onSearch(e.target.value)}
        style={{
          marginLeft: 'auto', padding: '5px 12px', borderRadius: 99,
          border: '1px solid var(--color-border)', background: 'var(--color-surface)',
          color: 'var(--color-text)', fontSize: 12, fontFamily: 'var(--font-ui)',
          outline: 'none', width: 220,
        }}
        onFocus={e => e.target.style.borderColor = 'var(--color-accent)'}
        onBlur={e => e.target.style.borderColor = 'var(--color-border)'}
      />
    </div>
  )
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [stats, setStats]               = useState(null)
  const [assets, setAssets]             = useState([])
  const [total, setTotal]               = useState(0)
  const [page, setPage]                 = useState(0)
  const [bandFilter, setBandFilter]     = useState('')
  const [classFilter, setClassFilter]   = useState('')
  const [search, setSearch]             = useState('')
  const [loading, setLoading]           = useState(true)
  const [error, setError]               = useState('')
  const [selectedAsset, setSelectedAsset] = useState(null)
  const [networkData, setNetworkData]   = useState(null)
  const [geojson, setGeojson]           = useState(null)

  const limit = 50

  useEffect(() => {
    setLoading(true); setError('')
    Promise.all([
      analysisApi.stats(),
      assetsApi.list({ skip: page * limit, limit, risk_band: bandFilter || undefined }),
      assetsApi.networkStats().catch(() => ({ data: null })),
      assetsApi.mapData().catch(() => ({ data: null })),
    ])
      .then(([statsRes, assetsRes, netRes, mapRes]) => {
        setStats(statsRes.data)
        setAssets(assetsRes.data.assets)
        setTotal(assetsRes.data.total)
        setNetworkData(netRes.data)
        setGeojson(mapRes.data)
      })
      .catch(err => setError(err.response?.data?.detail || 'Failed to load dashboard data'))
      .finally(() => setLoading(false))
  }, [page, bandFilter])

  const filteredAssets = assets.filter(a => {
    if (classFilter && a.road_class !== classFilter) return false
    if (search) {
      const q = search.toLowerCase()
      if (!(a.road_name?.toLowerCase().includes(q) || a.nsg_ref?.toLowerCase().includes(q))) return false
    }
    return true
  })

  const handleRowClick    = (asset) => setSelectedAsset(prev => prev?.nsg_ref === asset.nsg_ref ? null : asset)
  const handleBandFilter  = (band)  => { setBandFilter(band); setPage(0); setSelectedAsset(null) }
  const handleMapClick    = (nsgRef) => {
    const found = assets.find(a => a.nsg_ref === nsgRef)
    if (found) setSelectedAsset(prev => prev?.nsg_ref === nsgRef ? null : found)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {error && <div className="alert alert-error">{error}</div>}

      {/* Map command centre grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12, height: 480 }}>
        {/* Left — network map */}
        <NetworkMapCard
          geojson={geojson}
          networkData={networkData}
          onFeatureClick={handleMapClick}
        />

        {/* Right — stacked cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, height: '100%' }}>
          <RedNetworkCard stats={stats} />
          <RiskMixCard stats={stats} />
          <PrioritySectionsCard
            assets={filteredAssets}
            onRowClick={handleRowClick}
            selectedNsgRef={selectedAsset?.nsg_ref}
          />
        </div>
      </div>

      {/* Priority list */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h2 style={{ fontSize: 14, fontWeight: 500, color: 'var(--color-text)' }}>Priority asset list</h2>
          <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
            {total.toLocaleString()} assets
          </span>
        </div>

        <FilterBar
          bandFilter={bandFilter}   onBandFilter={handleBandFilter}
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
