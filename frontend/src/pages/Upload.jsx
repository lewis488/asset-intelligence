import { useRef, useState } from 'react'
import { assetsApi } from '../api/client'

// ── Validation result display ─────────────────────────────────────────────────

function ValidationPanel({ result }) {
  if (!result) return null
  const { errors = [], warnings = [], info = [] } = result

  return (
    <div style={{ marginTop: 10 }}>
      {errors.length > 0 && (
        <div className="alert alert-error" style={{ marginTop: 0 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>
            Upload blocked — {errors.length} error{errors.length !== 1 ? 's' : ''} to resolve
          </div>
          {errors.map((e, i) => (
            <div key={i} style={{ marginBottom: 6, fontSize: 13 }}>
              {e.column && (
                <code style={{ background: 'var(--color-red-bg)', padding: '1px 5px', borderRadius: 3, marginRight: 6, fontSize: 11.5 }}>
                  {e.column}
                </code>
              )}
              {e.message}
            </div>
          ))}
        </div>
      )}
      {warnings.length > 0 && (
        <div className="alert alert-warn" style={{ marginTop: 8 }}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>
            {warnings.length} warning{warnings.length !== 1 ? 's' : ''}
          </div>
          {warnings.map((w, i) => (
            <div key={i} style={{ marginBottom: 4, fontSize: 13 }}>
              {(w.column || w) && (
                <code style={{ background: 'var(--color-amber-bg)', padding: '1px 5px', borderRadius: 3, marginRight: 6, fontSize: 11.5 }}>
                  {w.column || ''}
                </code>
              )}
              {w.message || w}
            </div>
          ))}
        </div>
      )}
      {info.length > 0 && (
        <div style={{ marginTop: 8, paddingLeft: 2 }}>
          {info.map((m, i) => (
            <div key={i} style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 2 }}>
              {m.message || m}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function _extractValidationFailure(err) {
  const detail = err?.response?.data?.detail
  if (detail && typeof detail === 'object' && Array.isArray(detail.errors)) {
    return detail
  }
  return null
}

function _extractErrorMessage(err) {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return err?.message || 'Upload failed'
}

function NetworkUploadBlock() {
  const [result, setResult] = useState(null)
  const [error, setError]   = useState('')
  const [valFailure, setValFailure] = useState(null)
  const [loading, setLoading] = useState(false)
  const ref = useRef()
  const [over, setOver] = useState(false)

  const handle = async (file) => {
    if (!file) return
    setLoading(true); setError(''); setResult(null); setValFailure(null)
    try { setResult((await assetsApi.uploadNetwork(file)).data) }
    catch (err) {
      const vf = _extractValidationFailure(err)
      if (vf) setValFailure(vf)
      else setError(_extractErrorMessage(err))
    }
    finally { setLoading(false) }
  }

  const cov = result?.coverage_analysis
  const val = result?.validation
  return (
    <div className="card" style={{ marginBottom: 18, borderLeft: '4px solid var(--accent)' }}>
      <h2 style={{ fontSize: 15, fontWeight: 700 }}>Road Network (Shapefile)</h2>
      <p style={{ color: 'var(--muted)', fontSize: 13, marginTop: 3, marginBottom: 12 }}>
        Road network master register. Establishes the NSG inventory and geometry.
        Upload as <strong>.gpkg</strong> or <strong>.zip</strong> containing .shp/.shx/.dbf/.prj files.
        Applies road class and ownership filters, then aggregates to one row per NSG.
      </p>
      <div
        className={`dropzone${over ? ' over' : ''}`}
        onClick={() => ref.current.click()}
        onDragOver={e => { e.preventDefault(); setOver(true) }}
        onDragLeave={() => setOver(false)}
        onDrop={e => { e.preventDefault(); setOver(false); handle(e.dataTransfer.files[0]) }}
      >
        <input ref={ref} type="file" accept=".gpkg,.zip,.shp" style={{ display: 'none' }} onChange={e => handle(e.target.files[0])} />
        <div className="dz-icon">{loading ? '⏳' : '🗺'}</div>
        <p><strong>Click to browse</strong> or drag here</p>
        <p style={{ marginTop: 3, fontSize: 11.5, color: 'var(--muted)' }}>.gpkg or .zip — large files may take 1–2 minutes</p>
      </div>
      {loading && <div className="alert alert-info" style={{ marginTop: 10 }}>Processing network file… please wait.</div>}
      {error   && <div className="alert alert-error" style={{ marginTop: 10 }}>{error}</div>}
      {valFailure && <ValidationPanel result={valFailure} />}
      {result  && (
        <>
          <div className="alert alert-success" style={{ marginTop: 10 }}>
            <div>Ingested <strong>{result.nsgs_ingested.toLocaleString()}</strong> NSGs · <strong>{result.total_length_km.toLocaleString()}km</strong> total network</div>
            {result.by_class && (
              <div style={{ marginTop: 5, fontSize: 12 }}>
                {Object.entries(result.by_class).map(([cls, km]) => `${cls}: ${km}km`).join(' | ')}
              </div>
            )}
            {cov && (
              <div style={{ marginTop: 8, borderTop: '0.5px solid var(--color-green)', paddingTop: 8 }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>Coverage analysis ({cov.nsgs_matched_to_assets} of {result.nsgs_ingested} NSGs matched to asset records)</div>
                <div style={{ fontSize: 12, display: 'flex', flexWrap: 'wrap', gap: '4px 16px' }}>
                  <span>SCANNER: {cov.nsgs_with_scanner}</span>
                  <span>CVI: {cov.nsgs_with_cvi}</span>
                  <span>SCRIM: {cov.nsgs_with_scrim}</span>
                  <span>Reactive: {cov.nsgs_with_reactive}</span>
                  <span>No data: {cov.nsgs_with_no_data}</span>
                </div>
              </div>
            )}
          </div>
          {val?.warnings?.length > 0 && (
            <div className="alert alert-warn" style={{ marginTop: 8 }}>
              <strong>Uploaded with {val.warnings.length} warning{val.warnings.length !== 1 ? 's' : ''}</strong>
              {val.warnings.map((w, i) => (
                <div key={i} style={{ marginTop: 4, fontSize: 13 }}>{w.message || w}</div>
              ))}
            </div>
          )}
          {val?.info?.length > 0 && (
            <div style={{ marginTop: 6 }}>
              {val.info.map((m, i) => (
                <div key={i} style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 2 }}>{m.message || m}</div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── Schema reference data ─────────────────────────────────────────────────────
const SCANNER_SCHEMA = [
  { col: 'NSG',                       type: 'string',  req: true,  note: 'NSG/USRN section reference (unique identifier)' },
  { col: 'ROAD_NAME',                 type: 'string',  req: true,  note: 'Road name' },
  { col: 'PARISH',                    type: 'string',  req: false, note: 'Parish or locality' },
  { col: 'ROAD_CLASS',                type: 'string',  req: false, note: 'A, BC, or U' },
  { col: 'LENGTH_M',                  type: 'number',  req: false, note: 'Section length in metres' },
  { col: 'SURVEY_YEAR',               type: 'integer', req: false, note: 'Year of survey (e.g. 2024)' },
  { col: 'AVG_CI',                    type: 'number',  req: true,  note: 'Average Condition Index — 0–150+, lower = better condition' },
  { col: 'DEFECT_OVERALL_PCT',        type: 'decimal', req: false, note: 'Proportion of section with any defect (0.0–1.0)' },
  { col: 'DEFECT_RUTTING_PCT',        type: 'decimal', req: false, note: 'Proportion with rutting defect' },
  { col: 'DEFECT_CRACKING_PCT',       type: 'decimal', req: false, note: 'Proportion with cracking defect' },
  { col: 'DEFECT_TEXTURE_PCT',        type: 'decimal', req: false, note: 'Proportion with texture defect' },
  { col: 'DEFECT_LPV_PCT',            type: 'decimal', req: false, note: 'Proportion with LPV defect' },
  { col: 'AMBER_LENGTH_M',            type: 'number',  req: false, note: 'Length in metres in Amber RCI band' },
  { col: 'AMBER_PCT',                 type: 'decimal', req: false, note: 'Proportion of section in Amber band (0.0–1.0)' },
  { col: 'AMBER_RUTTING',             type: 'decimal', req: false, note: 'Amber rutting proportion' },
  { col: 'AMBER_CRACKING',            type: 'decimal', req: false, note: 'Amber cracking proportion' },
  { col: 'AMBER_TEXTURE',             type: 'decimal', req: false, note: 'Amber texture proportion' },
  { col: 'AMBER_LPV',                 type: 'decimal', req: false, note: 'Amber LPV proportion' },
  { col: 'RED_LENGTH_M',              type: 'number',  req: false, note: 'Length in metres in Red RCI band' },
  { col: 'RED_PCT',                   type: 'decimal', req: false, note: 'Proportion of section in Red band (0.0–1.0)' },
  { col: 'RED_RUTTING',               type: 'decimal', req: false, note: 'Red rutting proportion' },
  { col: 'RED_CRACKING',              type: 'decimal', req: false, note: 'Red cracking proportion' },
  { col: 'RED_TEXTURE',               type: 'decimal', req: false, note: 'Red texture proportion' },
  { col: 'RED_LPV',                   type: 'decimal', req: false, note: 'Red LPV proportion' },
  { col: 'CI_CONTRIBUTION_RUTTING',   type: 'decimal', req: false, note: 'Rutting share of CI — proportional, all four sum to ~1.0' },
  { col: 'CI_CONTRIBUTION_CRACKING',  type: 'decimal', req: false, note: 'Cracking share of CI' },
  { col: 'CI_CONTRIBUTION_TEXTURE',   type: 'decimal', req: false, note: 'Texture depth share of CI — drives defect driver scoring' },
  { col: 'CI_CONTRIBUTION_LPV',       type: 'decimal', req: false, note: 'LPV share of CI — dominant on B+C roads (~50%)' },
  { col: 'EDI_AVG',                   type: 'number',  req: false, note: 'Edge Deterioration Index — B+C roads only, leave blank for A roads' },
]

// ── Components ────────────────────────────────────────────────────────────────

function SchemaReport({ mapped, unmapped, sheets }) {
  if (!mapped?.length && !unmapped?.length) return null
  return (
    <div style={{ marginTop: 12 }}>
      {sheets?.length > 0 && (
        <div className="alert alert-info" style={{ marginBottom: 8 }}>
          <strong>Processed:</strong> {sheets.join(' | ')}
        </div>
      )}
      {mapped?.length > 0 && (
        <>
          <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 5 }}>Mapped ({mapped.length})</p>
          <div className="schema-grid" style={{ marginBottom: 8 }}>
            {mapped.map(c => <div key={c} className="schema-item mapped"><span>✓</span><span>{c}</span></div>)}
          </div>
        </>
      )}
      {unmapped?.length > 0 && (
        <>
          <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 5 }}>Unmapped — not ingested ({unmapped.length})</p>
          <div className="schema-grid">
            {unmapped.map(c => <div key={c} className="schema-item unmapped"><span>✗</span><span>{c}</span></div>)}
          </div>
        </>
      )}
    </div>
  )
}

function DropZone({ accept, hint, onFile, loading }) {
  const ref = useRef()
  const [over, setOver] = useState(false)
  const handle = (file) => { if (file) onFile(file) }
  return (
    <div className={`dropzone${over ? ' over' : ''}`}
      onClick={() => ref.current.click()}
      onDragOver={e => { e.preventDefault(); setOver(true) }}
      onDragLeave={() => setOver(false)}
      onDrop={e => { e.preventDefault(); setOver(false); handle(e.dataTransfer.files[0]) }}>
      <input ref={ref} type="file" accept={accept} onChange={e => handle(e.target.files[0])} />
      <div className="dz-icon">{loading ? '⏳' : '📄'}</div>
      <p><strong>Click to browse</strong> or drag here</p>
      <p style={{ marginTop: 3, fontSize: 11.5, color: 'var(--muted)' }}>{hint}</p>
    </div>
  )
}

function UploadBlock({ title, desc, accept, hint, uploadFn, templateUrl, children }) {
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handle = async (file) => {
    setLoading(true); setError(''); setResult(null)
    try { setResult((await uploadFn(file)).data) }
    catch (err) { setError(err.response?.data?.detail || 'Upload failed') }
    finally { setLoading(false) }
  }

  return (
    <div className="card" style={{ marginBottom: 18 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div>
          <h2 style={{ fontSize: 15, fontWeight: 600 }}>{title}</h2>
          <p style={{ color: 'var(--muted)', fontSize: 13, marginTop: 3 }}>{desc}</p>
        </div>
        {templateUrl && (
          <a href={templateUrl} download
            style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '6px 12px', background: '#f1f5f9', border: '1px solid var(--border)', borderRadius: 7, fontSize: 12.5, color: 'var(--text)', textDecoration: 'none', whiteSpace: 'nowrap', flexShrink: 0 }}>
            ⬇ CSV Template
          </a>
        )}
      </div>

      <DropZone accept={accept} hint={hint} onFile={handle} loading={loading} />

      {loading && <div className="alert alert-info" style={{ marginTop: 10 }}>Processing file…</div>}
      {error   && <div className="alert alert-error" style={{ marginTop: 10 }}>{error}</div>}
      {result  && (
        <>
          <div className="alert alert-success" style={{ marginTop: 10 }}>
            Ingested <strong>{result.ingested_rows}</strong> of {result.total_rows} rows successfully.
          </div>
          <SchemaReport mapped={result.mapped_columns} unmapped={result.unmapped_columns} sheets={result.sheets_processed} />
        </>
      )}

      {children}
    </div>
  )
}

function ScannerSchemaTable() {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ marginTop: 14, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
      <button className="btn btn-secondary btn-sm" onClick={() => setOpen(v => !v)}>
        {open ? '▲ Hide' : '▼ Show'} column reference ({SCANNER_SCHEMA.length} columns)
      </button>

      {open && (
        <div style={{ marginTop: 12, overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Column name</th>
                <th>Type</th>
                <th>Required</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {SCANNER_SCHEMA.map(({ col, type, req, note }) => (
                <tr key={col}>
                  <td>
                    <code style={{ fontFamily: 'monospace', fontSize: 11.5, background: '#f1f5f9', padding: '1px 5px', borderRadius: 3 }}>
                      {col}
                    </code>
                  </td>
                  <td style={{ color: 'var(--muted)', fontSize: 12 }}>{type}</td>
                  <td>
                    {req
                      ? <span style={{ color: 'var(--critical)', fontWeight: 600, fontSize: 11.5 }}>Required</span>
                      : <span style={{ color: 'var(--muted)', fontSize: 11.5 }}>Optional</span>}
                  </td>
                  <td style={{ color: 'var(--muted)', fontSize: 12 }}>{note}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="alert alert-info" style={{ marginTop: 10 }}>
            <strong>Decimal values</strong> (0.0–1.0) represent proportions. <strong>CI values</strong> are raw RCI numbers (0–150+, lower = better condition). <strong>EDI_AVG</strong> is only applicable to B+C roads — leave blank for A roads.
          </div>
        </div>
      )}
    </div>
  )
}

function RawUploadBlock({ title, desc, accept, hint, uploadFn }) {
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [valFailure, setValFailure] = useState(null)
  const [loading, setLoading] = useState(false)

  const handle = async (file) => {
    setLoading(true); setError(''); setResult(null); setValFailure(null)
    try {
      setResult((await uploadFn(file)).data)
    } catch (err) {
      const vf = _extractValidationFailure(err)
      if (vf) setValFailure(vf)
      else setError(_extractErrorMessage(err))
    } finally { setLoading(false) }
  }

  const val = result?.validation

  return (
    <div className="card" style={{ marginBottom: 18 }}>
      <h2 style={{ fontSize: 15, fontWeight: 600 }}>{title}</h2>
      <p style={{ color: 'var(--muted)', fontSize: 13, marginTop: 3, marginBottom: 12 }}>{desc}</p>

      <DropZone accept={accept} hint={hint} onFile={handle} loading={loading} />

      {loading && (
        <div className="alert alert-info" style={{ marginTop: 10 }}>
          Processing file… Large files may take up to 5 minutes — please wait.
        </div>
      )}
      {error && <div className="alert alert-error" style={{ marginTop: 10 }}>{error}</div>}
      {valFailure && <ValidationPanel result={valFailure} />}
      {result && (
        <>
          <div className="alert alert-success" style={{ marginTop: 10 }}>
            <div>
              Ingested <strong>{result.records_ingested}</strong> aggregated records —&nbsp;
              <strong>{result.assets_created}</strong> new assets,&nbsp;
              <strong>{result.assets_updated}</strong> updated.
            </div>
            {result.survey_years?.length > 0 && (
              <div style={{ marginTop: 4, fontSize: 13 }}>
                Survey years found: <strong>{result.survey_years.join(', ')}</strong>
              </div>
            )}
            {result.unmapped_columns?.length > 0 && (
              <div style={{ marginTop: 6, fontSize: 12, color: 'var(--muted)' }}>
                Unrecognised columns (ignored): {result.unmapped_columns.join(', ')}
              </div>
            )}
          </div>
          {val?.warnings?.length > 0 && (
            <div className="alert alert-warn" style={{ marginTop: 8 }}>
              <strong>Uploaded with {val.warnings.length} warning{val.warnings.length !== 1 ? 's' : ''}</strong>
              {val.warnings.map((w, i) => (
                <div key={i} style={{ marginTop: 4, fontSize: 13 }}>{w.message || w}</div>
              ))}
            </div>
          )}
          {val?.info?.length > 0 && (
            <div style={{ marginTop: 6 }}>
              {val.info.map((m, i) => (
                <div key={i} style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 2 }}>{m.message || m}</div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function ReactiveRawUploadBlock({ title, desc, accept, hint, uploadFn }) {
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [valFailure, setValFailure] = useState(null)
  const [loading, setLoading] = useState(false)

  const handle = async (file) => {
    setLoading(true); setError(''); setResult(null); setValFailure(null)
    try {
      setResult((await uploadFn(file)).data)
    } catch (err) {
      const vf = _extractValidationFailure(err)
      if (vf) setValFailure(vf)
      else setError(_extractErrorMessage(err))
    } finally { setLoading(false) }
  }

  const val = result?.validation

  return (
    <div className="card" style={{ marginBottom: 18 }}>
      <h2 style={{ fontSize: 15, fontWeight: 600 }}>{title}</h2>
      <p style={{ color: 'var(--muted)', fontSize: 13, marginTop: 3, marginBottom: 12 }}>{desc}</p>

      <DropZone accept={accept} hint={hint} onFile={handle} loading={loading} />

      {loading && (
        <div className="alert alert-info" style={{ marginTop: 10 }}>
          Processing file… Large files may take up to 5 minutes — please wait.
        </div>
      )}
      {error && <div className="alert alert-error" style={{ marginTop: 10 }}>{error}</div>}
      {valFailure && <ValidationPanel result={valFailure} />}
      {result && (
        <>
          <div className="alert alert-success" style={{ marginTop: 10 }}>
            <div>
              <strong>{result.jobs_ingested}</strong> jobs ingested,&nbsp;
              <strong>{result.jobs_skipped}</strong> skipped (duplicates),&nbsp;
              <strong>{result.jobs_filtered_out}</strong> filtered out (non-condition types).
            </div>
            <div style={{ marginTop: 4, fontSize: 13 }}>
              <strong>{result.assets_created}</strong> new assets created.&nbsp;
              <strong>{result.aggregates_rebuilt}</strong> NSG aggregates rebuilt.
            </div>
            {result.years_found?.length > 0 && (
              <div style={{ marginTop: 4, fontSize: 13 }}>
                Years: <strong>{result.years_found.join(', ')}</strong>
              </div>
            )}
            {result.job_type_breakdown && Object.keys(result.job_type_breakdown).length > 0 && (
              <div style={{ marginTop: 6, fontSize: 12, color: 'var(--muted)' }}>
                By type:&nbsp;
                {Object.entries(result.job_type_breakdown).map(([k, v]) => `${k}: ${v}`).join(' | ')}
              </div>
            )}
          </div>
          {val?.warnings?.length > 0 && (
            <div className="alert alert-warn" style={{ marginTop: 8 }}>
              <strong>Uploaded with {val.warnings.length} warning{val.warnings.length !== 1 ? 's' : ''}</strong>
              {val.warnings.map((w, i) => (
                <div key={i} style={{ marginTop: 4, fontSize: 13 }}>{w.message || w}</div>
              ))}
            </div>
          )}
          {val?.info?.length > 0 && (
            <div style={{ marginTop: 6 }}>
              {val.info.map((m, i) => (
                <div key={i} style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 2 }}>{m.message || m}</div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Upload() {
  const [showAliases, setShowAliases] = useState(false)
  const [aliasData, setAliasData] = useState(null)

  const loadAliases = async () => {
    if (!aliasData) setAliasData((await assetsApi.aliases()).data)
    setShowAliases(v => !v)
  }

  return (
    <div>
      <div className="page-header">
        <h1>Upload Data</h1>
        <p>Import SCANNER condition survey data (CSV or Excel), CVI records, and reactive maintenance jobs.</p>
      </div>

      <NetworkUploadBlock />

      <UploadBlock
        title="SCANNER Condition Data"
        desc="Upload SCANNER survey data as a flat CSV (recommended) or as a formatted HMDIF Excel file. CI contributions drive the defect driver scoring."
        accept=".csv,.xlsx,.xls"
        hint=".csv (recommended) or .xlsx — see column reference below"
        uploadFn={assetsApi.uploadScanner}
        templateUrl="/assets/schema/scanner-template"
      >
        <ScannerSchemaTable />
      </UploadBlock>

      <UploadBlock
        title="CVI Survey Data"
        desc="Coarse Visual Inspection data for unclassified roads. BV224b thresholds (Structural ≥ 85, Edge ≥ 50, Wearing Course ≥ 60) applied automatically."
        accept=".csv"
        hint="CSV with NSG/USRN, STRUCTURAL_CI, EDGE_CI, WEARING_COURSE_CI columns"
        uploadFn={assetsApi.uploadCvi}
      />

      <UploadBlock
        title="Reactive Maintenance Jobs"
        desc="Reactive job orders including defect type, response category, date and cost. Used in the reactive frequency scoring layer."
        accept=".csv"
        hint="CSV with NSG, JOB_TYPE, DEFECT_TYPE, JOB_DATE, COST_GBP, RESPONSE_CATEGORY"
        uploadFn={assetsApi.uploadReactive}
      />

      <div style={{ borderTop: '2px solid var(--border)', margin: '28px 0 20px', paddingTop: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Raw Confirm Export</h2>
        <p style={{ color: 'var(--muted)', fontSize: 13, marginBottom: 18 }}>
          Direct exports from Confirm — no pre-processing needed. 10m interval rows are aggregated
          automatically to one record per NSG per survey year on ingestion. Accepts .xlsx or .csv.
        </p>

        <RawUploadBlock
          title="SCANNER Raw (Confirm Export)"
          desc="Direct export from Confirm. Columns: NSG, FEATURE_ID, ROAD_NAME, START_CHAINAGE, END_CHAINAGE, OFFSET, FEATURE_GROUP, LANE, OBSERVATION, CI_VALUE, SURVEY_NUMBER, SURVEY_DATE"
          accept=".xlsx,.csv"
          hint=".xlsx or .csv — direct Confirm SCANNER export, no formatting required"
          uploadFn={assetsApi.uploadScannerRaw}
        />

        <RawUploadBlock
          title="CVI Raw (Confirm Export)"
          desc="Direct CVI export from Confirm. Columns: NSG, FEATURE_ID, ROAD_NAME, START_CHAINAGE, END_CHAINAGE, CI_STRUC, CI_WCRSE, CI_EDGE, CI_OVRLL, PARISH, SECTIONLEN, SURVEY_NUMBER, SURVEY_DATE, SURVEY_NAME, OFFSET"
          accept=".xlsx,.csv"
          hint=".xlsx or .csv — direct Confirm CVI export, variable section lengths"
          uploadFn={assetsApi.uploadCviRaw}
        />

        <RawUploadBlock
          title="SCRIM Raw (Confirm Export)"
          desc="Direct SCRIM MSSC export from Confirm. Columns: NSG, FEATURE_ID, ROAD_NAME, PARISH, ILCT, SFC, SFCT, XDIF, STARTCHAIN, ENDCHAIN, XSP_CODE, OFFSET, SURVEYNUMB, SURVEYDATE, SURVEY_NAME"
          accept=".xlsx,.csv"
          hint=".xlsx or .csv — direct Confirm SCRIM export, SFC=0 rows excluded from averages"
          uploadFn={assetsApi.uploadScrimRaw}
        />

        <ReactiveRawUploadBlock
          title="Reactive Jobs (Confirm Export)"
          desc="Confirm reactive jobs export. Platform filters to condition-relevant job types (potholes, patching, edge, drainage) and aggregates per NSG per year. Columns: job_number, site_code, site_name, job_entry_date, actual_comp_date, priority_name, job_type_name, status_name, district_name, locality_name, town_name, road_class, easting, northing"
          accept=".xlsx,.csv"
          hint=".xlsx or .csv — direct Confirm reactive export, footway and OOH jobs excluded automatically"
          uploadFn={assetsApi.uploadReactiveRaw}
        />
      </div>

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2 style={{ fontSize: 15, fontWeight: 600 }}>Full Column Alias Reference</h2>
            <p style={{ color: 'var(--muted)', fontSize: 13 }}>All accepted column name variants for each upload type</p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={loadAliases}>{showAliases ? 'Hide' : 'Show'}</button>
        </div>

        {showAliases && aliasData && (
          <div style={{ marginTop: 16 }}>
            {Object.entries(aliasData).map(([uploadType, fields]) => (
              <div key={uploadType} style={{ marginBottom: 20 }}>
                <h3 style={{ fontSize: 13.5, fontWeight: 600, marginBottom: 4, textTransform: 'capitalize' }}>
                  {uploadType.replace(/_/g, ' ')}
                </h3>
                {fields.description && <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>{fields.description}</p>}
                {fields.columns || (typeof fields === 'object' && !fields.description && !fields.section_groups) ? (
                  <table className="data-table">
                    <thead><tr><th>Field</th><th>Accepted column names</th></tr></thead>
                    <tbody>
                      {Object.entries(fields.columns || fields).map(([f, aliases]) => (
                        <tr key={f}>
                          <td><code style={{ fontFamily: 'monospace', background: '#f1f5f9', padding: '1px 5px', borderRadius: 4, fontSize: 11.5 }}>{f}</code></td>
                          <td style={{ color: 'var(--muted)', fontSize: 12 }}>{Array.isArray(aliases) ? aliases.join(', ') : JSON.stringify(aliases)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <pre style={{ fontSize: 11.5, background: '#f8fafc', padding: 10, borderRadius: 7, overflow: 'auto' }}>
                    {JSON.stringify(fields, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
