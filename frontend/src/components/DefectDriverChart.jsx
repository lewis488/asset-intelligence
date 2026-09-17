import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

const COLOURS = {
  LPV: '#3b82f6',      // blue  — structural roughness
  Rutting: '#ef4444',  // red   — structural deformation
  Cracking: '#f59e0b', // amber — surface/structural
  Texture: '#10b981',  // green — surface treatment
}

const LABELS = {
  LPV: 'LPV (ride quality)',
  Rutting: 'Rutting',
  Cracking: 'Cracking',
  Texture: 'Texture Depth',
}

function buildData(scannerData) {
  if (!scannerData) return []
  const { ci_contribution_lpv, ci_contribution_rutting, ci_contribution_cracking, ci_contribution_texture } = scannerData
  return [
    { key: 'LPV',      value: ci_contribution_lpv      || 0 },
    { key: 'Rutting',  value: ci_contribution_rutting  || 0 },
    { key: 'Cracking', value: ci_contribution_cracking || 0 },
    { key: 'Texture',  value: ci_contribution_texture  || 0 },
  ].filter(d => d.value > 0.001)
   .map(d => ({ ...d, name: LABELS[d.key] }))
}

function buildNetworkData(roadClass) {
  // WSCC benchmark data from knowledge base
  if (roadClass === 'A') {
    return [
      { key: 'Texture',  name: 'Texture Depth', value: 0.434 },
      { key: 'LPV',      name: 'LPV (ride quality)', value: 0.323 },
      { key: 'Cracking', name: 'Cracking', value: 0.205 },
      { key: 'Rutting',  name: 'Rutting', value: 0.038 },
    ]
  }
  return [
    { key: 'LPV',      name: 'LPV (ride quality)', value: 0.507 },
    { key: 'Texture',  name: 'Texture Depth', value: 0.261 },
    { key: 'Cracking', name: 'Cracking', value: 0.174 },
    { key: 'Rutting',  name: 'Rutting', value: 0.055 },
  ]
}

const pctFmt = (v) => `${(v * 100).toFixed(1)}%`

export default function DefectDriverChart({ scannerData, title, networkMode, roadClass }) {
  const data = networkMode ? buildNetworkData(roadClass) : buildData(scannerData)

  if (!data.length) return (
    <div style={{ padding: 20, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
      No CI contribution data available for this asset.
    </div>
  )

  return (
    <div>
      {title && <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>{title}</h3>}
      {networkMode && (
        <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>
          WSCC network benchmark — {roadClass === 'A' ? 'A roads: texture-dominant (surface focus)' : 'B+C roads: LPV-dominant (structural focus)'}
        </p>
      )}
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            outerRadius={75}
            innerRadius={28}
            dataKey="value"
            label={({ name, value }) => `${name}: ${pctFmt(value)}`}
            labelLine={false}
          >
            {data.map(entry => (
              <Cell key={entry.key} fill={COLOURS[entry.key] || '#94a3b8'} />
            ))}
          </Pie>
          <Tooltip formatter={(v) => pctFmt(v)} />
          <Legend
            formatter={(value) => <span style={{ fontSize: 12 }}>{value}</span>}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
