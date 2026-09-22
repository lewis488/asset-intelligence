import { Fragment, useEffect, useRef, useState } from 'react'
import 'leaflet/dist/leaflet.css'
import api, { vaisalaApi } from '../api/client'
import VaisalaSectionDetailPanel from '../components/VaisalaSectionDetailPanel'

const RAG_COLOUR    = { Red: '#C0453A', Amber: '#D89A3D', Green: '#4A8B6F' }
const RAG_COLOUR_BG = { Red: '#FBEAE8', Amber: '#FCF3E3', Green: '#EBF3EE' }
const RAG_COLOUR_TX = { Red: '#B0483C', Amber: '#B87A1E', Green: '#4A7A62' }
const NETWORKS = [
  { value: 'stroud', label: 'Gloucestershire / Stroud' },
  { value: 'wscc',   label: 'West Sussex (WSCC)' },
]
const TABS = [
  { key: 'list1', tag: 'Native', name: 'List 1', desc: 'Road Surface Condition' },
  { key: 'list2', tag: 'Native', name: 'List 2', desc: 'Asphalt Condition' },
  { key: 'list3', tag: 'Native', name: 'List 3', desc: 'PAS 2161' },
  { key: 'list4', tag: 'Computed', name: 'List 4', desc: 'Weighted Score' },
  { key: 'correlation', tag: 'Analysis', name: 'Correlation', desc: 'Cross-list agreement' },
  { key: 'qc', tag: 'Quality', name: 'QC', desc: 'Data confidence' },
  { key: 'map', tag: 'Visual', name: 'Map', desc: 'Network overview' },
]

// ─── Spearman helpers ──────────────────────────────────────────────────────
function computeRanks(values) {
  const indexed = values.map((v, i) => ({ v, i })).filter(x => x.v != null && !isNaN(x.v))
  indexed.sort((a, b) => a.v - b.v)
  const ranks = new Array(values.length).fill(null)
  let i = 0
  while (i < indexed.length) {
    let j = i
    while (j < indexed.length - 1 && indexed[j + 1].v === indexed[j].v) j++
    const avg = (i + j) / 2 + 1
    for (let k = i; k <= j; k++) ranks[indexed[k].i] = avg
    i = j + 1
  }
  return ranks
}

function pearsonCorr(xs, ys) {
  const pairs = xs.map((x, i) => [x, ys[i]]).filter(([x, y]) => x != null && y != null)
  if (pairs.length < 3) return null
  const n = pairs.length
  const xm = pairs.reduce((s, [x]) => s + x, 0) / n
  const ym = pairs.reduce((s, [, y]) => s + y, 0) / n
  let num = 0, xss = 0, yss = 0
  for (const [x, y] of pairs) {
    num += (x - xm) * (y - ym)
    xss += (x - xm) ** 2
    yss += (y - ym) ** 2
  }
  if (xss === 0 || yss === 0) return null
  return num / Math.sqrt(xss * yss)
}

function pct75(arr) {
  const sorted = arr.filter(v => v != null && !isNaN(v)).sort((a, b) => a - b)
  if (!sorted.length) return null
  return sorted[Math.floor(sorted.length * 0.75)]
}

// ─── Small shared components ──────────────────────────────────────────────
function RagStrip({ stats }) {
  if (!stats) return null
  const total = stats.section_count || 1
  return (
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
      {['Red', 'Amber', 'Green'].map(band => {
        const count = stats.rag_counts?.[band] ?? 0
        const km = stats.rag_length_km?.[band] ?? 0
        const pct = ((count / total) * 100).toFixed(1)
        return (
          <div key={band} className="card" style={{ flex: '1 1 160px', borderTop: `3px solid ${RAG_COLOUR[band]}`, padding: '14px 18px' }}>
            <div style={{ fontSize: 26, fontWeight: 500, color: RAG_COLOUR_TX[band] }}>{count}</div>
            <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--color-text)', marginTop: 2 }}>{band}</div>
            <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 2 }}>{km} km · {pct}%</div>
          </div>
        )
      })}
      <div className="card" style={{ flex: '1 1 160px', padding: '14px 18px' }}>
        <div style={{ fontSize: 26, fontWeight: 500, color: 'var(--color-text)' }}>{stats.total_length_km}</div>
        <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--color-text)', marginTop: 2 }}>Total km</div>
        <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 2 }}>{total} sections</div>
      </div>
    </div>
  )
}

function DriftWarning({ survey }) {
  if (!survey?.has_weight_drift) return null
  return (
    <div className="alert alert-error" style={{ marginBottom: 16 }}>
      <strong>RAG weight drift detected.</strong> Defect weights used for scoring differ from those the
      Red/Amber thresholds (4.0 / 1.8) were derived against. RAG banding may not be fully reliable.
    </div>
  )
}

function DirectionNote({ children }) {
  return (
    <div style={{ fontSize: 12, color: 'var(--color-text-muted)', fontStyle: 'italic', marginBottom: 12,
      padding: '8px 12px', background: 'var(--color-accent-soft)', borderRadius: 6, borderLeft: '3px solid var(--color-accent)' }}>
      {children}
    </div>
  )
}

// ─── Upload step indicator ────────────────────────────────────────────────
const UPLOAD_STEPS = ['Uploading', 'Parsing', 'Scoring', 'Complete']

function StepIndicator({ step }) {
  const current = UPLOAD_STEPS.indexOf(step)
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', margin: '20px 0 8px' }}>
      {UPLOAD_STEPS.map((s, i) => {
        const done = current > i
        const active = current === i
        return (
          <Fragment key={s}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 64 }}>
              <div style={{
                width: 30, height: 30, borderRadius: '50%',
                background: done ? 'var(--color-low)' : active ? 'var(--color-blue)' : 'var(--color-border)',
                color: done || active ? '#fff' : 'var(--color-text-muted)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 13, fontWeight: 700, transition: 'background 0.25s',
                boxShadow: active ? '0 0 0 3px rgba(59,130,246,0.25)' : 'none',
              }}>
                {done ? '✓' : active ? <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> : i + 1}
              </div>
              <div style={{
                fontSize: 11, marginTop: 5, textAlign: 'center',
                color: active ? 'var(--color-blue)' : done ? 'var(--color-low)' : 'var(--color-text-muted)',
                fontWeight: active || done ? 600 : 400,
              }}>{s}</div>
            </div>
            {i < UPLOAD_STEPS.length - 1 && (
              <div style={{
                flex: 1, height: 2, marginTop: 14,
                background: done ? 'var(--color-low)' : 'var(--color-border)',
                transition: 'background 0.25s',
              }} />
            )}
          </Fragment>
        )
      })}
    </div>
  )
}

// ─── Defect weight defaults (mirrors RAG_VALIDATED_WEIGHTS in vaisala_scoring.py) ──
const DEFAULT_WEIGHTS = {
  'Alligator cracking': 8,
  'Minor longitudinal cracking': 1,
  'Moderate longitudinal cracking': 3,
  'Severe longitudinal cracking': 6,
  'Wheel track cracking': 6,
  'Minor transverse cracking': 1,
  'Moderate transverse cracking': 3,
  'Severe transverse cracking': 6,
  'Minor pothole': 4,
  'Moderate pothole': 7,
  'Severe pothole': 10,
  'Left edge deterioration': 3,
  'Right edge deterioration': 3,
  'Moderate fretting': 2,
  'Severe fretting': 4,
  'Defective asphalt overlay': 4,
  'Binder bleeding': 5,
  'Subsidence': 10,
}

const WEIGHT_GROUPS = [
  { label: 'Structural', keys: ['Subsidence', 'Severe pothole', 'Wheel track cracking', 'Severe longitudinal cracking', 'Severe transverse cracking', 'Alligator cracking'], colour: '#c0432f' },
  { label: 'Moderate defects', keys: ['Moderate pothole', 'Moderate longitudinal cracking', 'Moderate transverse cracking', 'Defective asphalt overlay'], colour: '#d9a51c' },
  { label: 'Surface / minor', keys: ['Minor pothole', 'Minor longitudinal cracking', 'Minor transverse cracking', 'Severe fretting', 'Moderate fretting', 'Binder bleeding'], colour: '#3a7d44' },
  { label: 'Edge', keys: ['Left edge deterioration', 'Right edge deterioration'], colour: '#6366f1' },
]

function WeightSliders({ weights, onChange }) {
  return (
    <div style={{ marginTop: 4 }}>
      {WEIGHT_GROUPS.map(grp => (
        <div key={grp.label} style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: grp.colour, textTransform: 'uppercase',
            letterSpacing: '0.05em', marginBottom: 8 }}>{grp.label}</div>
          {grp.keys.map(key => (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
              <div style={{ flex: 1, fontSize: 12, color: 'var(--text)' }}>{key}</div>
              <input type="range" min={0} max={15} step={0.5} value={weights[key] ?? DEFAULT_WEIGHTS[key]}
                onChange={e => onChange(key, parseFloat(e.target.value))}
                style={{ width: 120, accentColor: grp.colour }} />
              <div style={{ width: 28, textAlign: 'right', fontSize: 12, fontWeight: 600,
                color: weights[key] !== DEFAULT_WEIGHTS[key] ? grp.colour : 'var(--muted)' }}>
                {(weights[key] ?? DEFAULT_WEIGHTS[key]).toFixed(1)}
              </div>
              {weights[key] !== undefined && weights[key] !== DEFAULT_WEIGHTS[key] && (
                <button onClick={() => onChange(key, DEFAULT_WEIGHTS[key])}
                  title="Reset to default"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 11,
                    color: 'var(--muted)', padding: '0 2px', lineHeight: 1 }}>↺</button>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

// ─── Upload panel ─────────────────────────────────────────────────────────
function UploadPanel({ onUploaded }) {
  const [network, setNetwork] = useState('stroud')
  const [mode, setMode] = useState('raw')
  const [dedupStrategy, setDedupStrategy] = useState('latest')
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [uploadStep, setUploadStep] = useState(null) // null | UPLOAD_STEPS[n] | 'error'
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [showWeights, setShowWeights] = useState(false)
  const [weights, setWeights] = useState({})
  const inputRef = useRef()
  const timers = useRef([])

  const accept = mode === 'raw' ? '.xlsx,.xls,.csv' : '.zip'
  const busy = uploadStep && uploadStep !== 'Complete' && uploadStep !== 'error'
  const weightsDirty = Object.keys(weights).some(k => weights[k] !== DEFAULT_WEIGHTS[k])

  const clearTimers = () => { timers.current.forEach(clearTimeout); timers.current = [] }

  const pickFile = (f) => { setFile(f); setResult(null); setError(''); setUploadStep(null) }

  const handleDrop = (e) => {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) pickFile(f)
  }

  const handleWeightChange = (key, val) => setWeights(prev => ({ ...prev, [key]: val }))

  const activeWeights = weightsDirty
    ? { ...DEFAULT_WEIGHTS, ...weights }
    : null  // null = use server defaults

  const submit = async () => {
    if (!file) return
    setError(''); setResult(null)
    setUploadStep('Uploading')
    timers.current.push(setTimeout(() => setUploadStep('Parsing'), 700))
    timers.current.push(setTimeout(() => setUploadStep('Scoring'), 1600))
    try {
      const res = mode === 'raw'
        ? await vaisalaApi.uploadRaw(file, network, activeWeights, dedupStrategy)
        : await vaisalaApi.uploadShp(file, network)
      clearTimers()
      setUploadStep('Complete')
      setResult(res.data)
      onUploaded(res.data)
    } catch (e) {
      clearTimers()
      setUploadStep('error')
      setError(e.response?.data?.detail || 'Upload failed')
    }
  }

  const reset = () => {
    clearTimers(); setFile(null); setUploadStep(null); setResult(null); setError('')
    if (inputRef.current) inputRef.current.value = ''
  }

  const rag = result?.rag_summary || {}
  const ragTotal = (rag.Red || 0) + (rag.Amber || 0) + (rag.Green || 0)

  return (
    <div className="card" style={{ marginBottom: 24 }}>
      <h2 style={{ fontSize: 14, fontWeight: 500, marginBottom: 16, color: 'var(--color-text)' }}>Upload Vaisala Survey</h2>

      {/* Controls */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
        <div>
          <label style={{ fontSize: 10, color: 'var(--color-text-muted)', display: 'block', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 500 }}>Network</label>
          <select value={network} onChange={e => setNetwork(e.target.value)} disabled={busy}
            style={{ padding: '7px 10px', borderRadius: 6, border: '1px solid var(--color-border)', background: 'var(--color-page)', color: 'var(--color-text)', fontSize: 13 }}>
            {NETWORKS.map(n => <option key={n.value} value={n.value}>{n.label}</option>)}
          </select>
        </div>
        <div>
          <label style={{ fontSize: 10, color: 'var(--color-text-muted)', display: 'block', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 500 }}>File type</label>
          <select value={mode} onChange={e => { setMode(e.target.value); reset() }} disabled={busy}
            style={{ padding: '7px 10px', borderRadius: 6, border: '1px solid var(--color-border)', background: 'var(--color-page)', color: 'var(--color-text)', fontSize: 13 }}>
            <option value="raw">Raw interval data (XLSX / CSV) — scored here</option>
            <option value="shp">Scored SHP export from priority_dst.html (ZIP)</option>
          </select>
        </div>
        {mode === 'raw' && (
          <div>
            <label style={{ fontSize: 10, color: 'var(--color-text-muted)', display: 'block', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 500 }}>
              Multiple passes
            </label>
            <select value={dedupStrategy} onChange={e => setDedupStrategy(e.target.value)} disabled={busy}
              title="When a section-interval was surveyed on multiple passes, resolve by keeping most recent (Time UTC) or leave duplicates in."
              style={{ padding: '7px 10px', borderRadius: 6, border: '1px solid var(--color-border)', background: 'var(--color-page)', color: 'var(--color-text)', fontSize: 13 }}>
              <option value="latest">Keep most recent (Time UTC)</option>
              <option value="none">Don't deduplicate</option>
            </select>
          </div>
        )}
      </div>

      {/* Weight configuration — raw mode only */}
      {mode === 'raw' && !uploadStep && (
        <div style={{ marginBottom: 14 }}>
          <button
            onClick={() => setShowWeights(v => !v)}
            style={{
              background: 'none', border: `1px solid ${weightsDirty ? 'var(--color-blue)' : 'var(--border)'}`,
              borderRadius: 6, padding: '5px 12px', fontSize: 12, cursor: 'pointer',
              color: weightsDirty ? 'var(--color-blue)' : 'var(--muted)',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
            <span>{showWeights ? '▲' : '▼'}</span>
            <span>Defect weights</span>
            {weightsDirty && <span style={{ fontWeight: 700 }}>· custom</span>}
            {!weightsDirty && <span style={{ opacity: 0.7 }}>· RAG-validated defaults</span>}
          </button>

          {showWeights && (
            <div style={{
              marginTop: 10, padding: '14px 16px',
              border: '1px solid var(--border)', borderRadius: 8,
              background: 'var(--bg-subtle, #f8f9fa)',
            }}>
              {weightsDirty && (
                <div style={{
                  marginBottom: 12, padding: '8px 12px', borderRadius: 6,
                  background: 'var(--color-amber-dim)', border: '1px solid rgba(245,166,35,0.3)',
                  fontSize: 12, color: 'var(--color-amber)', lineHeight: 1.5,
                }}>
                  <strong>Custom weights active.</strong> The RAG thresholds (Red ≥ 4.0 · Amber ≥ 1.8) were
                  derived against the default weight set. Custom weights may produce unreliable RAG banding.
                  <button onClick={() => setWeights({})}
                    style={{ marginLeft: 10, background: 'none', border: '1px solid rgba(245,166,35,0.4)',
                      borderRadius: 4, padding: '1px 8px', fontSize: 11, cursor: 'pointer', color: 'var(--color-amber)' }}>
                    Reset all to defaults
                  </button>
                </div>
              )}
              <WeightSliders weights={weights} onChange={handleWeightChange} />
            </div>
          )}
        </div>
      )}

      {/* Drop zone — hidden while processing or showing result */}
      {!uploadStep && (
        <div
          onDrop={handleDrop}
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onClick={() => inputRef.current?.click()}
          style={{
            border: `2px dashed ${dragging ? 'var(--color-blue)' : file ? 'var(--color-low)' : 'var(--color-border)'}`,
            borderRadius: 10, padding: '36px 24px', textAlign: 'center', cursor: 'pointer',
            background: dragging ? 'var(--color-blue-dim)' : file ? 'var(--color-low-dim)' : 'transparent',
            transition: 'all 0.15s',
          }}>
          <div style={{ fontSize: 32, marginBottom: 10, userSelect: 'none' }}>
            {file ? '📄' : dragging ? '📂' : '⬆️'}
          </div>
          {file ? (
            <>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{file.name}</div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
                {(file.size / 1024 / 1024).toFixed(2)} MB · Click to change file
              </div>
            </>
          ) : (
            <>
              <div style={{ fontWeight: 600, fontSize: 14 }}>
                {dragging ? 'Drop to select' : 'Drag & drop or click to browse'}
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 5 }}>
                {mode === 'raw'
                  ? 'XLSX, XLS or CSV — raw Vaisala interval data'
                  : 'ZIP — scored SHP export from priority_dst.html'}
              </div>
            </>
          )}
          <input ref={inputRef} type="file" accept={accept}
            onChange={e => { const f = e.target.files?.[0]; if (f) pickFile(f) }}
            style={{ display: 'none' }} />
        </div>
      )}

      {/* Upload button */}
      {!uploadStep && file && (
        <button className="btn btn-primary" onClick={submit}
          style={{ marginTop: 14, width: '100%', padding: '11px 0', fontSize: 14, fontWeight: 600 }}>
          Upload &amp; Score
        </button>
      )}

      {/* Step progress */}
      {uploadStep && uploadStep !== 'error' && <StepIndicator step={uploadStep} />}

      {/* Error */}
      {uploadStep === 'error' && (
        <div>
          <div className="alert alert-error" style={{ marginTop: 10 }}>{error}</div>
          <button className="btn btn-secondary" onClick={reset}
            style={{ marginTop: 8, fontSize: 13 }}>Try again</button>
        </div>
      )}

      {/* Result summary */}
      {result && uploadStep === 'Complete' && (
        <div style={{
          marginTop: 14, padding: '16px 18px',
          background: 'var(--color-low-dim)', borderRadius: 8, border: '1px solid rgba(52,211,153,0.2)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--color-low)' }}>
              ✓ {result.section_count} sections scored · {result.source_filename}
            </div>
            <button className="btn btn-secondary" onClick={reset}
              style={{ fontSize: 12, padding: '4px 12px' }}>Upload another</button>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            {[['Red', '#c0432f'], ['Amber', '#d9a51c'], ['Green', '#3a7d44']].map(([band, colour]) => {
              const count = rag[band] || 0
              const pct = ragTotal ? ((count / ragTotal) * 100).toFixed(0) : 0
              return (
                <div key={band} style={{
                  flex: 1, padding: '10px 12px', borderRadius: 7,
                  borderTop: `3px solid ${colour}`, background: 'var(--color-surface)',
                }}>
                  <div style={{ fontSize: 22, fontWeight: 700, color: colour }}>{count}</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{band} · {pct}%</div>
                </div>
              )
            })}
          </div>
          {result.has_weight_drift && (
            <div className="alert alert-error" style={{ marginTop: 10, fontSize: 12 }}>
              RAG weight drift detected — banding may not be fully reliable.
            </div>
          )}
          {mode === 'raw' && result.dup_groups_resolved > 0 && dedupStrategy === 'latest' && (
            <div style={{ marginTop: 10, fontSize: 12, color: 'var(--muted)' }}>
              {result.dup_groups_resolved.toLocaleString()} section-interval(s) had repeat surveys · kept most recent by Time UTC.
            </div>
          )}
          {mode === 'raw' && dedupStrategy === 'none' && (
            <div style={{ marginTop: 10, fontSize: 12, color: 'var(--muted)' }}>
              Deduplication off · every survey pass counted separately.
            </div>
          )}
          {mode === 'raw' && result.info_meta && Object.values(result.info_meta).some(Boolean) && (
            <div style={{ marginTop: 12, padding: '10px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12, color: 'var(--muted)' }}>
              {result.info_meta.district && <div>Client / District: <strong style={{ color: 'var(--text)' }}>{result.info_meta.district}</strong></div>}
              {result.info_meta.road_class && <div>Road class filter: <strong style={{ color: 'var(--text)' }}>{result.info_meta.road_class}</strong></div>}
              {(result.info_meta.from_date || result.info_meta.to_date) && (
                <div>Survey window: <strong style={{ color: 'var(--text)' }}>{(result.info_meta.from_date || '—').slice(0, 10)} → {(result.info_meta.to_date || '—').slice(0, 10)}</strong></div>
              )}
              {result.info_meta.interval_length && <div>Interval length: <strong style={{ color: 'var(--text)' }}>{result.info_meta.interval_length}m</strong></div>}
              {result.info_meta.multiple_drives && <div>Multiple drives: <strong style={{ color: 'var(--text)' }}>{result.info_meta.multiple_drives}</strong></div>}
            </div>
          )}
          {mode === 'raw' && (
            <div style={{ marginTop: 10, fontSize: 11, color: 'var(--muted)' }}>
              Scored with RAG-validated weights · Red ≥ 4.0 · Amber ≥ 1.8 · Green &lt; 1.8
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Tab bar ──────────────────────────────────────────────────────────────
function TabBar({ activeTab, onChange }) {
  return (
    <div className="tab-row">
      {TABS.map(t => {
        const active = activeTab === t.key
        return (
          <button
            key={t.key}
            onClick={() => onChange(t.key)}
            title={`${t.tag} · ${t.desc}`}
            className={`tab-btn${active ? ' tab-btn--active' : ''}`}
          >
            {t.name}
          </button>
        )
      })}
    </div>
  )
}

const MERGE_SCALES = [
  { key: 'section', label: 'Section', desc: 'as-scored aggregate' },
  { key: '100m',    label: '100m',    desc: 'rolling window' },
  { key: '10m',     label: '10m',     desc: 'raw intervals' },
]

function MergeScaleToggle({ value, onChange, disabledScales = [] }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 10, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 500 }}>Merge scale</span>
      <div className="seg-control">
        {MERGE_SCALES.map(s => {
          const active = s.key === value
          const disabled = disabledScales.includes(s.key)
          return (
            <button
              key={s.key}
              onClick={() => !disabled && onChange(s.key)}
              disabled={disabled}
              title={disabled ? 'Urban always scores at whole section length' : s.desc}
              className={`seg-btn${active ? ' seg-btn--active' : ''}`}
              style={{ opacity: disabled ? 0.35 : 1, cursor: disabled ? 'not-allowed' : 'pointer' }}
            >
              {s.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

const SPLITS = [
  { key: 'combined', label: 'Combined', desc: 'urban section + rural at scale' },
  { key: 'urban',    label: 'Urban',    desc: 'urban roads only, always section' },
  { key: 'rural',    label: 'Rural',    desc: 'rural roads only, at selected scale' },
]

function SplitToggle({ value, onChange }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 10, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 500 }}>Split</span>
      <div className="seg-control">
        {SPLITS.map(s => {
          const active = s.key === value
          return (
            <button
              key={s.key}
              onClick={() => onChange(s.key)}
              title={s.desc}
              className={`seg-btn${active ? ' seg-btn--active' : ''}`}
            >
              {s.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

const TREATMENT_MODES = [
  { key: 'defect',     label: 'Defect pattern', desc: 'engineering-based: treatment from which defects are present' },
  { key: 'percentile', label: 'Percentile',     desc: 'score-based: worst X% of rows in this view get each treatment' },
]

function TreatmentModeToggle({ value, onChange }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 10, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 500 }}>Treatment</span>
      <div className="seg-control">
        {TREATMENT_MODES.map(s => {
          const active = s.key === value
          return (
            <button
              key={s.key}
              onClick={() => onChange(s.key)}
              title={s.desc}
              className={`seg-btn${active ? ' seg-btn--active' : ''}`}
            >
              {s.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ─── Generic list tab (Lists 1–4) ─────────────────────────────────────────
const LIST_CONFIG = {
  list1: {
    title: 'List 1 — Road Surface Condition',
    dirNote: 'Sorted ascending — lower RSC score = worse condition (Class 1 = worst). Native Vaisala output.',
    sortBy: 'road_surface_condition',
    sortDir: 'asc',
    cols: [
      { key: 'section_ref', label: 'Section', mono: true },
      { key: 'road_name', label: 'Road', fallback: '—' },
      { key: 'length_m', label: 'Length (m)', right: true, fmt: v => v?.toFixed(0) },
      { key: 'road_surface_condition', label: 'RSC Score', right: true, bold: true, fmt: v => v?.toFixed(2) ?? '—' },
      { key: 'road_surface_condition_class', label: 'Class', fallback: '—' },
      { key: 'treatment', label: 'Treatment', fallback: '—', muted: true },
    ],
  },
  list2: {
    title: 'List 2 — Asphalt Condition',
    dirNote: 'Sorted ascending — lower asphalt score = worse condition. Native Vaisala output.',
    sortBy: 'asphalt_condition',
    sortDir: 'asc',
    cols: [
      { key: 'section_ref', label: 'Section', mono: true },
      { key: 'road_name', label: 'Road', fallback: '—' },
      { key: 'length_m', label: 'Length (m)', right: true, fmt: v => v?.toFixed(0) },
      { key: 'asphalt_condition', label: 'Asphalt Score', right: true, bold: true, fmt: v => v?.toFixed(2) ?? '—' },
      { key: 'asphalt_condition_class', label: 'Class', fallback: '—' },
      { key: 'treatment', label: 'Treatment', fallback: '—', muted: true },
    ],
  },
  list3: {
    title: 'List 3 — PAS 2161 RCM Category',
    dirNote: 'Sorted descending — higher category number = worse condition (Cat 4/5 = structural intervention required). Native Vaisala output.',
    sortBy: 'pas2161_category',
    sortDir: 'desc',
    cols: [
      { key: 'section_ref', label: 'Section', mono: true },
      { key: 'road_name', label: 'Road', fallback: '—' },
      { key: 'length_m', label: 'Length (m)', right: true, fmt: v => v?.toFixed(0) },
      { key: 'pas2161_category', label: 'PAS Category', bold: true, fallback: '—' },
      { key: 'rag_band', label: 'RAG', rag: true },
      { key: 'treatment', label: 'Treatment', fallback: '—', muted: true },
    ],
  },
  list4: {
    title: 'List 4 — Weighted Priority Score',
    dirNote: 'Sorted descending — higher weighted score = worse condition. Computed from RAG-validated defect weights; patching-only defects excluded.',
    sortBy: 'priority_score',
    sortDir: 'desc',
    cols: [
      { key: 'section_ref', label: 'Section', mono: true },
      { key: 'road_name', label: 'Road', fallback: '—' },
      { key: 'length_m', label: 'Length (m)', right: true, fmt: v => v?.toFixed(0) },
      { key: 'priority_score', label: 'Score', right: true, bold: true, fmt: v => v?.toFixed(2) ?? '—' },
      { key: 'worst_interval_score', label: 'Worst Int.', right: true, muted: true, fmt: v => v?.toFixed(2) ?? '—' },
      { key: 'rag_band', label: 'RAG', rag: true },
      { key: 'treatment', label: 'Treatment', fallback: '—', muted: true },
      { key: 'primary_defect', label: 'Primary Defect', fallback: '—', muted: true },
    ],
  },
}

function ListTab({ surveyId, mode, view, onRowClick, selectedSectionId }) {
  const cfg = LIST_CONFIG[mode]
  const { mergeScale, split, treatmentMode } = view
  const [sections, setSections] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [ragFilter, setRagFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const limit = 50

  const doExport = async (format) => {
    const ext = format === 'shp' ? 'zip' : format
    setExporting(true)
    try {
      const response = await api.get(`/vaisala/surveys/${surveyId}/export`, {
        responseType: 'blob',
        params: { merge_scale: mergeScale, split, treatment_mode: treatmentMode, format },
      })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      const scalePart = mergeScale && mergeScale !== 'section' ? `_${mergeScale}` : ''
      const splitPart = split && split !== 'combined' ? `_${split}` : ''
      const tmodePart = treatmentMode && treatmentMode !== 'defect' ? `_${treatmentMode}` : ''
      link.setAttribute('download', `vaisala_survey_${surveyId}${scalePart}${splitPart}${tmodePart}.${ext}`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (e) {
      const msg = e.response?.data?.detail || 'Export failed'
      alert(msg)
    } finally {
      setExporting(false)
    }
  }

  useEffect(() => {
    if (!surveyId) return
    setLoading(true)
    vaisalaApi.sections(surveyId, {
      skip: page * limit, limit,
      sort_by: cfg.sortBy, sort_dir: cfg.sortDir,
      rag_band: ragFilter || undefined,
      merge_scale: mergeScale,
      split,
      treatment_mode: treatmentMode,
    })
      .then(r => { setSections(r.data.sections); setTotal(r.data.total) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [surveyId, page, ragFilter, mode, mergeScale, split, treatmentMode])

  useEffect(() => { setPage(0); setRagFilter('') }, [mode, surveyId, mergeScale, split, treatmentMode])

  const hasNulls = sections.length > 0 && sections.every(s => s[cfg.sortBy] == null)

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600 }}>{cfg.title}</h2>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {mode === 'list4' && (
            <select value={ragFilter} onChange={e => { setRagFilter(e.target.value); setPage(0) }}
              style={{ padding: '5px 10px', borderRadius: 6, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)', fontSize: 13 }}>
              <option value="">All RAG bands</option>
              <option value="Red">Red</option>
              <option value="Amber">Amber</option>
              <option value="Green">Green</option>
            </select>
          )}
          <button className="btn btn-secondary" onClick={() => doExport('csv')} disabled={exporting}
            style={{ fontSize: 12, padding: '5px 12px' }}>
            {exporting ? 'Exporting…' : 'CSV'}
          </button>
          <button className="btn btn-secondary" onClick={() => doExport('xlsx')} disabled={exporting}
            style={{ fontSize: 12, padding: '5px 12px' }}>
            XLSX
          </button>
          <button className="btn btn-primary" onClick={() => doExport('shp')} disabled={exporting}
            title="Requires an active network geometry (upload one on the Map tab)"
            style={{ fontSize: 12, padding: '5px 12px' }}>
            SHP
          </button>
        </div>
      </div>

      <DirectionNote>
        {cfg.dirNote}
        {onRowClick && <span style={{ marginLeft: 10, color: 'var(--color-blue)', fontStyle: 'normal' }}>Click any row for full section detail and AI assessment.</span>}
      </DirectionNote>

      {hasNulls && (
        <div className="alert" style={{ marginBottom: 12, background: 'var(--bg-subtle, #f5f5f5)', border: '1px solid var(--border)', borderRadius: 6, padding: '10px 14px', fontSize: 13, color: 'var(--muted)' }}>
          No data for this field in the uploaded survey — this metric may not be present in the selected network's export format.
        </div>
      )}

      {loading ? (
        <div style={{ padding: 24, textAlign: 'center', color: 'var(--muted)' }}>Loading…</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border)' }}>
                {cfg.cols.map(c => (
                  <th key={c.key} style={{ padding: '8px 10px', textAlign: c.right ? 'right' : 'left',
                    fontWeight: 600, color: 'var(--muted)', whiteSpace: 'nowrap' }}>{c.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sections.map(s => (
                <tr key={s.id}
                  onClick={() => onRowClick?.(s)}
                  style={{
                    borderBottom: '1px solid var(--border)',
                    cursor: onRowClick ? 'pointer' : undefined,
                    background: s.id === selectedSectionId ? 'var(--color-amber-dim)' : undefined,
                  }}>
                  {cfg.cols.map(c => {
                    const raw = s[c.key]
                    if (c.rag) {
                      return (
                        <td key={c.key} style={{ padding: '8px 10px' }}>
                          {raw ? (
                            <span style={{
                              display: 'inline-block', padding: '2px 8px', borderRadius: 99, fontSize: 11, fontWeight: 700,
                              background: (RAG_COLOUR[raw] || '#888') + '22', color: RAG_COLOUR[raw] || '#888',
                            }}>{raw}</span>
                          ) : '—'}
                        </td>
                      )
                    }
                    const display = c.fmt ? c.fmt(raw) : (raw ?? c.fallback ?? '—')
                    // Append chunk_label under section_ref when a merged view emitted one
                    const extra = c.key === 'section_ref' && s.chunk_label
                      ? <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'monospace', marginTop: 2 }}>{s.chunk_label}</div>
                      : null
                    return (
                      <td key={c.key} style={{
                        padding: '8px 10px',
                        textAlign: c.right ? 'right' : 'left',
                        fontWeight: c.bold ? 600 : 400,
                        fontFamily: c.mono ? 'monospace' : undefined,
                        fontSize: c.mono ? 12 : undefined,
                        color: c.muted ? 'var(--muted)' : undefined,
                      }}>{display}{extra}</td>
                    )
                  })}
                </tr>
              ))}
              {!sections.length && (
                <tr><td colSpan={cfg.cols.length} style={{ padding: 24, textAlign: 'center', color: 'var(--muted)' }}>No sections found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {total > limit && (
        <div className="pagination" style={{ marginTop: 12 }}>
          <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>← Prev</button>
          <span className="pg-info">Page {page + 1} of {Math.ceil(total / limit)} · {total} total</span>
          <button onClick={() => setPage(p => p + 1)} disabled={(page + 1) * limit >= total}>Next →</button>
        </div>
      )}
    </div>
  )
}

// ─── Correlation tab ──────────────────────────────────────────────────────
const CORR_LISTS = [
  { key: 'l1', label: 'List 1 (RSC)', field: 'road_surface_condition', invert: true },
  { key: 'l2', label: 'List 2 (Asphalt)', field: 'asphalt_condition', invert: true },
  { key: 'l3', label: 'List 3 (PAS)', field: 'pas2161_category', numeric: true },
  { key: 'l4', label: 'List 4 (Score)', field: 'priority_score' },
]

function corrColor(r) {
  if (r == null) return '#888'
  if (r >= 0.7) return '#3a7d44'
  if (r >= 0.4) return '#d9a51c'
  return '#c0432f'
}

function CorrelationTab({ surveyId, view }) {
  const [sections, setSections] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!surveyId) return
    setLoading(true); setError('')
    vaisalaApi.allSections(surveyId, view)
      .then(r => setSections(r.data))
      .catch(() => setError('Failed to load sections'))
      .finally(() => setLoading(false))
  }, [surveyId, view.mergeScale, view.split, view.treatmentMode])

  if (loading) return <div className="card" style={{ padding: 32, textAlign: 'center', color: 'var(--muted)' }}>Computing correlation…</div>
  if (error) return <div className="card"><div className="alert alert-error">{error}</div></div>
  if (!sections) return null

  // Build severity arrays (higher = worse for all lists after normalisation)
  const sev = CORR_LISTS.map(L => {
    return sections.map(s => {
      let v = s[L.field]
      if (L.numeric) v = parseFloat(v)
      if (v == null || isNaN(v)) return null
      return L.invert ? -v : v
    })
  })

  // Filter to lists that have any data
  const activeLists = CORR_LISTS.filter((_, i) => sev[i].some(v => v != null))

  if (activeLists.length < 2) {
    return (
      <div className="card">
        <p style={{ color: 'var(--muted)', fontSize: 13 }}>
          At least two lists need data to compute correlation. This survey may not include RSC, asphalt, or PAS 2161 fields.
        </p>
      </div>
    )
  }

  const activeSev = activeLists.map((L, li) => {
    const idx = CORR_LISTS.indexOf(L)
    return sev[idx]
  })

  // Compute ranks and Spearman correlations
  const ranks = activeSev.map(computeRanks)
  const corrMatrix = activeLists.map((_, i) =>
    activeLists.map((_, j) => {
      if (i === j) return 1
      return pearsonCorr(ranks[i], ranks[j])
    })
  )

  // Worst quartile sets (top 25% by severity)
  const worstSets = activeSev.map(sv => {
    const threshold = pct75(sv.filter(v => v != null))
    if (threshold == null) return new Set()
    return new Set(sections.map((_, i) => i).filter(i => sv[i] != null && sv[i] >= threshold))
  })

  // Overlap between each pair
  const pairOverlaps = []
  for (let i = 0; i < activeLists.length; i++) {
    for (let j = i + 1; j < activeLists.length; j++) {
      const overlap = [...worstSets[i]].filter(idx => worstSets[j].has(idx))
      pairOverlaps.push({ a: activeLists[i].label, b: activeLists[j].label, count: overlap.length, total: sections.length, indices: overlap })
    }
  }

  // "All agree" — in worst quartile on ALL active lists
  const allAgreeIndices = [...worstSets[0]].filter(idx => worstSets.every(ws => ws.has(idx)))
  const allAgreeSections = allAgreeIndices.map(i => sections[i]).sort((a, b) => (b.priority_score || 0) - (a.priority_score || 0))

  return (
    <div>
      {/* Correlation matrix */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>Cross-List Correlation (Spearman ρ)</h2>
        <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>
          How consistently each pair of lists ranks sections by severity. ρ ≥ 0.7 = strong agreement · 0.4–0.7 = moderate · &lt; 0.4 = weak.
        </p>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr>
                <th style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: 'var(--muted)' }}></th>
                {activeLists.map(L => (
                  <th key={L.key} style={{ padding: '8px 12px', textAlign: 'center', fontWeight: 600, color: 'var(--muted)', whiteSpace: 'nowrap' }}>{L.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {activeLists.map((rowL, i) => (
                <tr key={rowL.key} style={{ borderTop: '1px solid var(--border)' }}>
                  <td style={{ padding: '8px 12px', fontWeight: 600, whiteSpace: 'nowrap' }}>{rowL.label}</td>
                  {activeLists.map((colL, j) => {
                    const r = corrMatrix[i][j]
                    return (
                      <td key={colL.key} style={{ padding: '8px 12px', textAlign: 'center',
                        background: i === j ? 'var(--bg-subtle, #f5f5f5)' : undefined }}>
                        {i === j ? '—' : (
                          <span style={{ fontWeight: 700, color: corrColor(r) }}>
                            {r != null ? r.toFixed(2) : 'n/a'}
                          </span>
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Overlap cards */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>Worst-Quartile Overlap</h2>
        <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>
          Sections in the worst 25% on both lists simultaneously. Higher overlap = lists agree on which roads are in worst condition.
        </p>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {pairOverlaps.map(p => {
            const pct = sections.length ? ((p.count / sections.length) * 100).toFixed(1) : '0'
            return (
              <div key={p.a + p.b} className="card" style={{ flex: '1 1 200px', padding: '14px 18px', borderTop: '3px solid var(--color-blue)' }}>
                <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {p.a} ↔ {p.b}
                </div>
                <div style={{ fontSize: 24, fontWeight: 700 }}>{p.count}</div>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>sections · {pct}% of network</div>
              </div>
            )
          })}
        </div>
      </div>

      {/* All-agree table */}
      <div className="card">
        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
          All-List Agreement — {allAgreeSections.length} sections
        </h2>
        <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12 }}>
          Sections in the worst quartile on <em>every</em> active list simultaneously — the highest-confidence candidates for intervention.
        </p>
        {allAgreeSections.length === 0 ? (
          <p style={{ color: 'var(--muted)', fontSize: 13 }}>No sections appear in the worst quartile on all lists.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)' }}>
                  {['Section', 'Road', 'Length (m)', 'Score', 'RSC', 'Asphalt', 'PAS', 'RAG', 'Treatment'].map(h => (
                    <th key={h} style={{ padding: '8px 10px', textAlign: 'left', fontWeight: 600, color: 'var(--muted)', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {allAgreeSections.map(s => (
                  <tr key={s.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px 10px', fontFamily: 'monospace', fontSize: 12 }}>{s.section_ref}</td>
                    <td style={{ padding: '8px 10px' }}>{s.road_name || '—'}</td>
                    <td style={{ padding: '8px 10px', textAlign: 'right' }}>{s.length_m?.toFixed(0)}</td>
                    <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600 }}>{s.priority_score?.toFixed(2) ?? '—'}</td>
                    <td style={{ padding: '8px 10px', textAlign: 'right' }}>{s.road_surface_condition?.toFixed(2) ?? '—'}</td>
                    <td style={{ padding: '8px 10px', textAlign: 'right' }}>{s.asphalt_condition?.toFixed(2) ?? '—'}</td>
                    <td style={{ padding: '8px 10px' }}>{s.pas2161_category ?? '—'}</td>
                    <td style={{ padding: '8px 10px' }}>
                      {s.rag_band ? (
                        <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 99, fontSize: 11, fontWeight: 700,
                          background: (RAG_COLOUR[s.rag_band] || '#888') + '22', color: RAG_COLOUR[s.rag_band] || '#888' }}>
                          {s.rag_band}
                        </span>
                      ) : '—'}
                    </td>
                    <td style={{ padding: '8px 10px', fontSize: 12, color: 'var(--muted)' }}>{s.treatment || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── QC tab ───────────────────────────────────────────────────────────────
const QC_BANDS = ['High', 'Medium', 'Low']
const BAND_COLOUR = { High: '#3a7d44', Medium: '#d9a51c', Low: '#c0432f', Unknown: '#888' }

function QCTab({ surveyId, view }) {
  const [sections, setSections] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!surveyId) return
    setLoading(true); setError('')
    vaisalaApi.allSections(surveyId, view)
      .then(r => setSections(r.data))
      .catch(() => setError('Failed to load sections'))
      .finally(() => setLoading(false))
  }, [surveyId, view.mergeScale, view.split, view.treatmentMode])

  if (loading) return <div className="card" style={{ padding: 32, textAlign: 'center', color: 'var(--muted)' }}>Loading QC data…</div>
  if (error) return <div className="card"><div className="alert alert-error">{error}</div></div>
  if (!sections) return null

  const hasQC = sections.some(s => s.qc_completeness_band != null || s.qc_reliability_band != null)

  if (!hasQC) {
    return (
      <div className="card">
        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Data QC — Completeness & Reliability</h2>
        <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.7 }}>
          <p>QC metrics are not available for this survey.</p>
          <p style={{ marginTop: 8 }}>
            Survey completeness and reading reliability fields are produced by a separate Vaisala QC process
            and are not present in the raw interval-level XLSX/CSV export. They are populated when uploading
            a pre-scored SHP export from <code>priority_dst.html</code>, which includes the QC output alongside the scored sections.
          </p>
          <p style={{ marginTop: 8 }}>
            To view QC data: re-run the scoring in <code>priority_dst.html</code>, export the SHP, and upload
            the resulting ZIP using the <em>Scored SHP export</em> option.
          </p>
        </div>
      </div>
    )
  }

  const totalLen = sections.reduce((s, r) => s + (r.length_m || 0), 0)

  function bandBuckets(bandField) {
    const b = { High: [], Medium: [], Low: [], Unknown: [] }
    sections.forEach(s => { (b[s[bandField]] || b.Unknown).push(s) })
    return b
  }
  function bandLenPct(buckets, band) {
    const len = buckets[band].reduce((s, r) => s + (r.length_m || 0), 0)
    return totalLen > 0 ? (len / totalLen * 100) : 0
  }
  function weightedAvg(field) {
    let sum = 0, w = 0
    sections.forEach(s => { if (s[field] != null && s.length_m > 0) { sum += s[field] * s.length_m; w += s.length_m } })
    return w > 0 ? sum / w : null
  }

  const cBuckets = bandBuckets('qc_completeness_band')
  const rBuckets = bandBuckets('qc_reliability_band')
  const avgC = weightedAvg('qc_completeness_pct')
  const avgR = weightedAvg('qc_reliability_pct')

  const worstC = sections.filter(s => s.qc_completeness_band === 'Low')
    .sort((a, b) => (a.qc_completeness_pct ?? 1) - (b.qc_completeness_pct ?? 1)).slice(0, 20)
  const worstR = sections.filter(s => s.qc_reliability_band === 'Low')
    .sort((a, b) => (a.qc_reliability_pct ?? 1) - (b.qc_reliability_pct ?? 1)).slice(0, 20)

  function BandStrip({ label, buckets, avg }) {
    return (
      <div className="card" style={{ flex: '1 1 300px' }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>{label}</div>
        {avg != null && (
          <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 12 }}>{(avg * 100).toFixed(0)}% <span style={{ fontSize: 13, fontWeight: 400, color: 'var(--muted)' }}>network avg.</span></div>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {QC_BANDS.map(band => {
            const pct = bandLenPct(buckets, band)
            return (
              <div key={band}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
                  <span style={{ color: BAND_COLOUR[band], fontWeight: 600 }}>{band}</span>
                  <span style={{ color: 'var(--muted)' }}>{pct.toFixed(1)}% of network length · {buckets[band].length} sections</span>
                </div>
                <div style={{ height: 6, borderRadius: 3, background: 'var(--border)' }}>
                  <div style={{ height: '100%', borderRadius: 3, background: BAND_COLOUR[band], width: `${pct}%` }} />
                </div>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  function QCTable({ title, rows, pctField }) {
    if (!rows.length) return null
    return (
      <div className="card" style={{ marginTop: 20 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>{title} — {rows.length} sections</h3>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border)' }}>
                {['Section', 'Road', 'Length (m)', '% Coverage', 'Score', 'RAG', 'Treatment'].map(h => (
                  <th key={h} style={{ padding: '8px 10px', textAlign: 'left', fontWeight: 600, color: 'var(--muted)', whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(s => (
                <tr key={s.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '8px 10px', fontFamily: 'monospace', fontSize: 12 }}>{s.section_ref}</td>
                  <td style={{ padding: '8px 10px' }}>{s.road_name || '—'}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'right' }}>{s.length_m?.toFixed(0)}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600, color: '#c0432f' }}>
                    {s[pctField] != null ? (s[pctField] * 100).toFixed(0) + '%' : '—'}
                  </td>
                  <td style={{ padding: '8px 10px', textAlign: 'right' }}>{s.priority_score?.toFixed(2) ?? '—'}</td>
                  <td style={{ padding: '8px 10px' }}>
                    {s.rag_band ? (
                      <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 99, fontSize: 11, fontWeight: 700,
                        background: (RAG_COLOUR[s.rag_band] || '#888') + '22', color: RAG_COLOUR[s.rag_band] || '#888' }}>
                        {s.rag_band}
                      </span>
                    ) : '—'}
                  </td>
                  <td style={{ padding: '8px 10px', fontSize: 12, color: 'var(--muted)' }}>{s.treatment || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="card" style={{ marginBottom: 16, fontSize: 13, color: 'var(--muted)', lineHeight: 1.7,
        borderLeft: '3px solid var(--color-blue)', paddingLeft: 14 }}>
        Two separate signals, kept apart deliberately.{' '}
        <strong style={{ color: 'var(--text)' }}>Completeness</strong>: how much of a section was physically surveyed (vehicle coverage).{' '}
        <strong style={{ color: 'var(--text)' }}>Reliability</strong>: of what WAS surveyed, how much Vaisala itself judged valid.{' '}
        A section can be Low on completeness with a perfectly clean reading over what was surveyed — neither says anything about road condition.
        Priority scores for sections Low on either measure should be treated as provisional.
      </div>

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 20 }}>
        <BandStrip label="Survey Completeness" buckets={cBuckets} avg={avgC} />
        <BandStrip label="Reading Reliability" buckets={rBuckets} avg={avgR} />
      </div>

      <QCTable title="Lowest Completeness (Low band)" rows={worstC} pctField="qc_completeness_pct" />
      <QCTable title="Lowest Reliability (Low band)" rows={worstR} pctField="qc_reliability_pct" />
    </div>
  )
}

// ─── Map tab ──────────────────────────────────────────────────────────────
function NetworkGeometryUploadPanel({ current, onUploaded }) {
  const [file, setFile] = useState(null)
  const [sectionField, setSectionField] = useState('')
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  const submit = async () => {
    if (!file) return
    setError(''); setUploading(true)
    try {
      const res = await vaisalaApi.uploadNetworkGeometry(file, sectionField || undefined)
      setFile(null); setSectionField('')
      onUploaded(res.data)
    } catch (e) {
      setError(e.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div style={{ padding: '10px 14px', border: '1px dashed var(--border)', borderRadius: 8, marginBottom: 12, fontSize: 13 }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <strong style={{ color: 'var(--text)' }}>Network geometry:</strong>
        {current?.active ? (
          <span style={{ color: 'var(--muted)' }}>
            {current.source_filename} · {current.feature_count?.toLocaleString()} features · key <code>{current.section_field}</code>
          </span>
        ) : (
          <span style={{ color: 'var(--muted)' }}>None loaded — upload a network shapefile ZIP to enable map join and SHP export.</span>
        )}
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 10, flexWrap: 'wrap' }}>
        <input type="file" accept=".zip" onChange={e => setFile(e.target.files[0] || null)} disabled={uploading}
          style={{ fontSize: 12 }} />
        <input type="text" placeholder="section_field (optional — auto-detect)" value={sectionField}
          onChange={e => setSectionField(e.target.value)} disabled={uploading}
          style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)', fontSize: 12, width: 260 }} />
        <button className="btn btn-secondary" onClick={submit} disabled={!file || uploading} style={{ fontSize: 12, padding: '4px 12px' }}>
          {uploading ? 'Uploading…' : 'Upload SHP zip'}
        </button>
        {error && <span style={{ color: 'var(--color-critical)', fontSize: 12 }}>{error}</span>}
      </div>
    </div>
  )
}

const MAP_TREATMENT_COLOURS = {
  'Resurfacing':        '#b23a28',
  'Patching':           '#d9862a',
  'Surface Dressing':   '#c9a227',
  'Micro-surfacing':    '#7d9e6a',
  'Monitor / Patching': '#5c8a99',
}

function _lerp(a, b, t) {
  const pa = a.match(/\w\w/g).map(x => parseInt(x, 16))
  const pb = b.match(/\w\w/g).map(x => parseInt(x, 16))
  return '#' + pa.map((v, i) => Math.round(v + (pb[i] - v) * t).toString(16).padStart(2, '0')).join('')
}

function scoreToColour(score) {
  if (score == null || isNaN(score)) return '#8a8d89'
  const t = Math.max(0, Math.min(1, score / 10))
  return t < 0.5 ? _lerp('#7a9b6e', '#d9a51c', t / 0.5) : _lerp('#d9a51c', '#c0432f', (t - 0.5) / 0.5)
}

function featureColour(props, mode) {
  if (!props?.matched) return '#666'
  if (mode === 'score') return scoreToColour(props.priority_score)
  if (mode === 'treatment') return MAP_TREATMENT_COLOURS[props.treatment] || '#8a8d89'
  const b = props.rag_band
  return b === 'Red' ? '#c0432f' : b === 'Amber' ? '#d9a51c' : b === 'Green' ? '#3a7d44' : '#888'
}

function MapTab({ surveyId, view }) {
  const [features, setFeatures] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [network, setNetwork] = useState(null)
  const [colourMode, setColourMode] = useState('rag')
  const [selectedFeature, setSelectedFeature] = useState(null)
  const mapRef = useRef(null)
  const layerRef = useRef(null)
  const basemapRef = useRef(null)

  const OS_KEY = import.meta.env.VITE_OS_MAPS_API_KEY

  const refreshNetwork = () => {
    vaisalaApi.currentNetworkGeometry().then(r => setNetwork(r.data)).catch(() => setNetwork(null))
  }

  useEffect(() => { refreshNetwork() }, [])

  useEffect(() => {
    if (!surveyId) return
    setLoading(true); setError('')
    vaisalaApi.networkFeatures(surveyId, view)
      .then(r => setFeatures(r.data))
      .catch(e => setError(e.response?.data?.detail || 'Failed to load features'))
      .finally(() => setLoading(false))
  }, [surveyId, view.mergeScale, view.split, view.treatmentMode, network?.id])

  // Init Leaflet map; destroy on unmount so orphaned event listeners don't accumulate
  useEffect(() => {
    const el = document.getElementById('vaisala-map')
    if (!el) return
    let cancelled = false
    import('leaflet').then(mod => {
      if (cancelled || mapRef.current) return
      const L = mod.default || mod
      const map = L.map(el, { preferCanvas: true }).setView([51.5, -2.2], 10)
      const tileUrl = OS_KEY
        ? `https://api.os.uk/maps/raster/v1/zxy/Light_3857/{z}/{x}/{y}.png?key=${OS_KEY}`
        : 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
      basemapRef.current = L.tileLayer(tileUrl, {
        maxZoom: 20,
        attribution: OS_KEY ? '© Crown copyright · Ordnance Survey' : '© OpenStreetMap contributors',
      }).addTo(map)
      mapRef.current = map
    })
    return () => {
      cancelled = true
      if (mapRef.current) { mapRef.current.remove(); mapRef.current = null }
      layerRef.current = null
      basemapRef.current = null
    }
  }, [OS_KEY])

  // Render feature layer whenever features / colour mode change
  useEffect(() => {
    if (!mapRef.current || !features) return
    import('leaflet').then(mod => {
      const L = mod.default || mod
      if (layerRef.current) layerRef.current.remove()
      if (!features.features?.length) { layerRef.current = null; return }
      const layer = L.geoJSON(features, {
        style: (f) => ({
          color: featureColour(f.properties, colourMode),
          weight: 3,
          opacity: f.properties?.matched ? 0.85 : 0.25,
        }),
        onEachFeature: (f, l) => {
          l.on('click', () => setSelectedFeature(f.properties || {}))
          l.on('mouseover', () => l.setStyle({ weight: 6 }))
          l.on('mouseout',  () => l.setStyle({ weight: 3 }))
        },
      })
      layer.addTo(mapRef.current)
      layerRef.current = layer
      try { mapRef.current.fitBounds(layer.getBounds(), { padding: [20, 20] }) } catch {}
    })
  }, [features, colourMode])

  const bandCounts = features?.features?.reduce((acc, f) => {
    const b = f.properties?.rag_band || 'Unmatched'
    acc[b] = (acc[b] || 0) + 1
    return acc
  }, {}) || {}

  return (
    <div className="card">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 10 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, margin: 0 }}>Network Map</h2>
        <SymbologyToggle value={colourMode} onChange={setColourMode} />
      </div>
      <NetworkGeometryUploadPanel current={network} onUploaded={() => refreshNetwork()} />
      {!OS_KEY && (
        <div className="alert" style={{ marginBottom: 10, padding: '8px 12px', borderRadius: 6, background: 'rgba(217,165,28,0.12)', border: '1px solid rgba(217,165,28,0.35)', fontSize: 12, color: 'var(--text)' }}>
          No OS Maps API key set (<code>VITE_OS_MAPS_API_KEY</code>) — falling back to OpenStreetMap tiles. Add a key from the OS Data Hub to switch to the OS Light basemap.
        </div>
      )}
      {loading && <div style={{ padding: 12, color: 'var(--muted)' }}>Loading features…</div>}
      {error && <div className="alert alert-error" style={{ marginBottom: 10 }}>{error}</div>}
      <div style={{ position: 'relative', display: 'grid', gridTemplateColumns: selectedFeature ? '1fr 340px' : '1fr', gap: 12 }}>
        <div style={{ position: 'relative' }}>
          <div id="vaisala-map" style={{ height: 520, borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border)' }} />
          <MapLegend mode={colourMode} />
        </div>
        {selectedFeature && (
          <SectionDetailPanel props={selectedFeature} onClose={() => setSelectedFeature(null)} />
        )}
      </div>
      {features && (
        <div style={{ marginTop: 10, fontSize: 12, color: 'var(--muted)' }}>
          {features.matched_features?.toLocaleString() || 0} / {features.total_features?.toLocaleString() || 0} features matched to survey rows ·
          Red {bandCounts.Red || 0} · Amber {bandCounts.Amber || 0} · Green {bandCounts.Green || 0}
          {bandCounts.Unmatched ? ` · Unmatched ${bandCounts.Unmatched}` : ''}
        </div>
      )}
    </div>
  )
}

const SYMBOLOGY_MODES = [
  { key: 'rag',       label: 'RAG band' },
  { key: 'score',     label: 'Weighted score' },
  { key: 'treatment', label: 'Treatment type' },
]

function SymbologyToggle({ value, onChange }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 12, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Symbology</span>
      <div style={{ display: 'flex', gap: 4 }}>
        {SYMBOLOGY_MODES.map(m => {
          const active = value === m.key
          return (
            <button key={m.key} onClick={() => onChange(m.key)}
              style={{
                padding: '4px 10px', borderRadius: 6,
                border: `1px solid ${active ? 'var(--color-blue)' : 'var(--border)'}`,
                background: active ? 'var(--color-blue)' : 'transparent',
                color: active ? '#fff' : 'var(--text)', cursor: 'pointer', fontSize: 12,
              }}>
              {m.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function MapLegend({ mode }) {
  const swatches = []
  if (mode === 'rag') {
    swatches.push(['Red', '#c0432f'], ['Amber', '#d9a51c'], ['Green', '#3a7d44'])
  } else if (mode === 'treatment') {
    Object.entries(MAP_TREATMENT_COLOURS).forEach(([k, v]) => swatches.push([k, v]))
  } else {
    swatches.push(
      ['0', scoreToColour(0)],
      ['2', scoreToColour(2)],
      ['4', scoreToColour(4)],
      ['6', scoreToColour(6)],
      ['8+', scoreToColour(9)],
    )
  }
  return (
    <div style={{
      position: 'absolute', bottom: 10, right: 10, zIndex: 500,
      background: 'rgba(20,22,24,0.85)', color: '#fff',
      padding: '8px 10px', borderRadius: 6, fontSize: 11,
      backdropFilter: 'blur(4px)', border: '1px solid rgba(255,255,255,0.1)',
    }}>
      <div style={{ opacity: 0.7, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: 10 }}>
        {mode === 'rag' ? 'RAG band' : mode === 'treatment' ? 'Treatment' : 'Weighted score'}
      </div>
      {swatches.map(([label, colour]) => (
        <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
          <span style={{ width: 14, height: 4, background: colour, display: 'inline-block', borderRadius: 2 }} />
          <span>{label}</span>
        </div>
      ))}
    </div>
  )
}

function SectionDetailPanel({ props, onClose }) {
  const p = props || {}
  const fmt = (v, dp = 2) => (v == null || isNaN(v)) ? '—' : Number(v).toFixed(dp)
  const pct = (v) => (v == null || isNaN(v)) ? '—' : `${Number(v).toFixed(1)}%`
  const ragColour = p.rag_band === 'Red' ? '#c0432f' : p.rag_band === 'Amber' ? '#d9a51c' : p.rag_band === 'Green' ? '#3a7d44' : '#888'
  const row = (k, v) => (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid var(--border)', gap: 8 }}>
      <span style={{ color: 'var(--muted)', fontSize: 12 }}>{k}</span>
      <span style={{ fontSize: 12, fontFamily: 'var(--font-data, monospace)', textAlign: 'right' }}>{v}</span>
    </div>
  )
  return (
    <div className="card" style={{ padding: 14, background: 'var(--color-surface)', border: '1px solid var(--border)', borderRadius: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <div>
          <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Section</div>
          <div style={{ fontSize: 15, fontWeight: 700, fontFamily: 'monospace' }}>{p.section_ref || p.section_key || '—'}</div>
          {p.chunk_label && <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'monospace' }}>{p.chunk_label}</div>}
        </div>
        <button onClick={onClose} style={{ background: 'transparent', border: '1px solid var(--border)', borderRadius: 4, padding: '2px 8px', color: 'var(--muted)', cursor: 'pointer', fontSize: 12 }}>×</button>
      </div>

      {!p.matched && (
        <div style={{ padding: 10, background: 'rgba(255,255,255,0.04)', borderRadius: 6, fontSize: 12, color: 'var(--muted)' }}>
          No scored data joined for this section — check the section_field on your network geometry upload.
        </div>
      )}

      {p.matched && (
        <>
          <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
            <span style={{ padding: '3px 10px', borderRadius: 99, background: ragColour + '22', color: ragColour, fontWeight: 700, fontSize: 12 }}>{p.rag_band || '—'}</span>
            <span style={{ padding: '3px 10px', borderRadius: 99, background: 'var(--color-surface-raised, rgba(255,255,255,0.04))', fontSize: 12 }}>{p.treatment || '—'}</span>
          </div>

          {row('Road', p.road_name || '—')}
          {row('Road class', p.road_class || '—')}
          {row('Net reference', p.net_reference || '—')}
          {row('Urban / Rural', p.urban_rural || '—')}
          {row('Length', p.length_m != null ? `${fmt(p.length_m, 0)} m` : '—')}
          {row('List 4 score', fmt(p.priority_score))}
          {row('Worst interval score', fmt(p.worst_interval_score))}

          <div style={{ marginTop: 10, marginBottom: 6, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)' }}>Defect breakdown</div>
          {row('Structural', pct(p.structural_pct))}
          {row('Alligator', pct(p.alligator_pct))}
          {row('Localised', pct(p.localised_pct))}
          {row('Edge', pct(p.edge_pct))}
          {row('Dressing', pct(p.dressing_pct))}
          {row('Micro', pct(p.micro_pct))}

          <div style={{ marginTop: 10, marginBottom: 6, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)' }}>Primary / secondary</div>
          {row('Primary defect', p.primary_defect || '—')}
          {row('Primary contribution', fmt(p.primary_defect_contribution))}
          {row('Secondary defect', p.secondary_defect || '—')}
          {row('Secondary contribution', fmt(p.secondary_defect_contribution))}

          <div style={{ marginTop: 10, marginBottom: 6, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)' }}>Source measures</div>
          {row('Road surface cond.', fmt(p.road_surface_condition))}
          {row('Asphalt cond.', fmt(p.asphalt_condition))}
          {row('PAS 2161', p.pas2161_category || '—')}
        </>
      )}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────
export default function Vaisala() {
  const [surveys, setSurveys] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [stats, setStats] = useState(null)
  const [loadingStats, setLoadingStats] = useState(false)
  const [activeTab, setActiveTab] = useState('list4')
  const [selectedSection, setSelectedSection] = useState(null)
  const [mergeScale, setMergeScale] = useState('section')
  const [split, setSplit] = useState('combined')
  const [treatmentMode, setTreatmentMode] = useState('defect')

  // Urban rows always score at whole section length (priority_dst.html brief) — force scale to
  // section whenever the Urban split is active so the toggle doesn't lie about the underlying data.
  useEffect(() => {
    if (split === 'urban' && mergeScale !== 'section') setMergeScale('section')
  }, [split, mergeScale])

  const view = { mergeScale, split, treatmentMode }

  const loadSurveys = () => {
    vaisalaApi.surveys().then(r => {
      setSurveys(r.data)
      if (!selectedId && r.data.length) setSelectedId(r.data[0].id)
    }).catch(() => {})
  }

  useEffect(() => { loadSurveys() }, [])

  useEffect(() => {
    if (!selectedId) return
    setLoadingStats(true)
    vaisalaApi.stats(selectedId, view)
      .then(r => setStats(r.data))
      .catch(() => setStats(null))
      .finally(() => setLoadingStats(false))
  }, [selectedId, mergeScale, split, treatmentMode])

  const handleUploaded = (result) => {
    loadSurveys()
    setSelectedId(result.survey_id)
    setActiveTab('list4')
    setSelectedSection(null)
  }

  const handleSectionClick = (section) => {
    setSelectedSection(prev => prev?.id === section.id ? null : section)
  }

  const selectedSurvey = surveys.find(s => s.id === selectedId)

  function renderTab() {
    if (!selectedId) return null
    if (activeTab === 'correlation') return <CorrelationTab surveyId={selectedId} view={view} />
    if (activeTab === 'qc') return <QCTab surveyId={selectedId} view={view} />
    if (activeTab === 'map') return <MapTab surveyId={selectedId} view={view} />
    return (
      <ListTab
        surveyId={selectedId}
        mode={activeTab}
        view={view}
        onRowClick={handleSectionClick}
        selectedSectionId={selectedSection?.id}
      />
    )
  }

  return (
    <div>
      <div className="page-header">
        <h1>Vaisala Survey Analysis</h1>
        <p>Road condition scoring · RAG banding · Treatment prioritisation</p>
      </div>

      {surveys.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <label style={{ fontSize: 13, color: 'var(--muted)', marginRight: 8 }}>Survey:</label>
          <select value={selectedId ?? ''} onChange={e => setSelectedId(Number(e.target.value))}
            style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)', fontSize: 13 }}>
            {surveys.map(s => (
              <option key={s.id} value={s.id}>
                {s.source_filename} · {s.network_key} · {new Date(s.imported_at).toLocaleDateString('en-GB')}
              </option>
            ))}
          </select>
        </div>
      )}

      <DriftWarning survey={selectedSurvey} />

      {loadingStats
        ? <div style={{ padding: 24, color: 'var(--muted)' }}>Loading stats…</div>
        : <RagStrip stats={stats} />
      }

      {selectedId && stats && (
        <div className="card" style={{ marginBottom: 20, padding: '12px 18px' }}>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', fontSize: 13 }}>
            {Object.entries(stats.top_treatments || {}).map(([t, n]) => (
              <span key={t}><strong>{n}</strong> <span style={{ color: 'var(--muted)' }}>{t}</span></span>
            ))}
          </div>
        </div>
      )}

      {selectedId && (
        <>
          <TabBar activeTab={activeTab} onChange={tab => { setActiveTab(tab); setSelectedSection(null) }} />
          {activeTab !== 'map' && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 20, alignItems: 'center', marginBottom: 16 }}>
              <MergeScaleToggle value={mergeScale} onChange={setMergeScale} disabledScales={split === 'urban' ? ['10m', '100m'] : []} />
              {stats?.has_urban_rural && <SplitToggle value={split} onChange={setSplit} />}
              {activeTab === 'list4' && <TreatmentModeToggle value={treatmentMode} onChange={setTreatmentMode} />}
            </div>
          )}
          {renderTab()}
        </>
      )}

      {!selectedId && surveys.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: '40px 32px', color: 'var(--muted)' }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>🛣️</div>
          <div style={{ fontWeight: 600, fontSize: 15, color: 'var(--text)', marginBottom: 8 }}>
            No surveys uploaded yet
          </div>
          <div style={{ fontSize: 13, lineHeight: 1.7, maxWidth: 460, margin: '0 auto' }}>
            Upload a raw Vaisala interval XLSX/CSV to score sections server-side, or a scored SHP export
            ZIP from <code>priority_dst.html</code> to import pre-scored results.
            RAG banding uses fixed evidence-derived thresholds: <strong>Red ≥ 4.0 · Amber ≥ 1.8</strong>.
          </div>
        </div>
      )}

      <div style={{ marginTop: 24 }}>
        <UploadPanel onUploaded={handleUploaded} />
      </div>

      {selectedSection && (
        <VaisalaSectionDetailPanel
          section={selectedSection}
          surveyMeta={selectedSurvey}
          onClose={() => setSelectedSection(null)}
        />
      )}
    </div>
  )
}
