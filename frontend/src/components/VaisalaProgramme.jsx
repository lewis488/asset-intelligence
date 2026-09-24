import { useEffect, useRef, useState } from 'react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import VaisalaActionDiagnostics from './VaisalaActionDiagnostics'
import VaisalaProgrammeDetail, { ACTIONS, STATUSES, controlStyle, displayValue, errorText } from './VaisalaProgrammeDetail'

const queueNotes = {
  engineer_assessment: 'Establish defect significance, mechanism, depth or edge support before selecting works.',
  evidence_validation: 'Check the supplied export and imagery first; obtain targeted verification where gaps remain.',
  treatment_appraisal: 'Compare conditional candidates after confirming site suitability and prerequisites.',
  monitor: 'Monitoring requires a documented client decision. No automatic monitoring rule is enabled.',
  no_action_indicated: 'Complete valid observations indicate no additional condition-led intervention; existing inspections continue.',
}
const emptyFilters = { action: '', search: '', scale: '', rag_band: '', evidence_status: '', review_status: '' }
const metres = value => value == null ? 'Unknown' : `${Number(value).toLocaleString('en-GB', { maximumFractionDigits: 1 })} m`
const date = value => value ? new Date(value).toLocaleString('en-GB') : 'Unknown date'

export default function VaisalaProgramme({ surveyId, survey, view }) {
  const { user } = useAuth()
  const canEdit = ['manager', 'admin'].includes(user?.role)
  const [programme, setProgramme] = useState(null)
  const [snapshots, setSnapshots] = useState([])
  const [snapshotId, setSnapshotId] = useState('')
  const [filters, setFilters] = useState(emptyFilters)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [selected, setSelected] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [reload, setReload] = useState(0)
  const saveKey = useRef(null)
  const detailRequest = useRef(0)
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const base = `/vaisala/surveys/${surveyId}`
  const endpoint = snapshotId ? `${base}/programmes/${snapshotId}` : `${base}/programme`
  const activeFilters = Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== ''))
  const params = { ...activeFilters, page, page_size: 50, ...(!snapshotId ? { merge_scale: view.mergeScale, split: view.split } : {}) }

  useEffect(() => {
    const controller = new AbortController()
    api.get(`${base}/programmes`, { signal: controller.signal }).then(r => setSnapshots(r.data)).catch(e => { if (e.code !== 'ERR_CANCELED') setError(errorText(e)) })
    return () => controller.abort()
  }, [base, reload])
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError('')
    api.get(endpoint, { params, signal: controller.signal }).then(r => setProgramme(r.data))
      .catch(e => { if (e.code !== 'ERR_CANCELED') { setError(errorText(e)); setProgramme(null) } })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [endpoint, view.mergeScale, view.split, filters, page, reload])
  useEffect(() => {
    setSnapshotId(''); setPage(1); setSelected(null); setFilters(emptyFilters)
    setNotice(''); saveKey.current = null; detailRequest.current += 1
  }, [surveyId, view.mergeScale, view.split])

  function changeFilter(key, value) { setFilters(f => ({ ...f, [key]: value })); setPage(1); setSelected(null); detailRequest.current += 1 }
  async function openItem(item) {
    const request = ++detailRequest.current
    setSelected(item); setDetailLoading(true)
    try {
      const { data } = await api.get(`${endpoint}/items/${encodeURIComponent(item.item_key)}`, {
        params: snapshotId ? {} : { merge_scale: view.mergeScale, split: view.split, policy_version: programme?.policy_version },
      })
      if (mounted.current && request === detailRequest.current) { setSelected(data); return true }
    } catch (e) { if (mounted.current && request === detailRequest.current) setError(errorText(e)) }
    finally { if (mounted.current && request === detailRequest.current) setDetailLoading(false) }
  }
  async function saveProgramme() {
    setBusy('save'); setError('')
    // Reuse a key after uncertain failures so retry cannot create duplicate snapshots.
    saveKey.current ||= crypto.randomUUID()
    try {
      const { data } = await api.post(`${base}/programmes`, { merge_scale: view.mergeScale, split: view.split, policy_version: programme.policy_version, idempotency_key: saveKey.current })
      if (!mounted.current) return
      setSnapshotId(String(data.id)); setSelected(null); setPage(1); setReload(n => n + 1)
      setNotice('Programme saved. Recommendations are frozen; reviews are recorded separately.'); saveKey.current = null
    } catch (e) { if (mounted.current) setError(errorText(e)) }
    finally { if (mounted.current) setBusy('') }
  }
  async function exportProgramme(format, filtered) {
    setBusy('export'); setError('')
    try {
      const { data } = await api.get(`${endpoint}/export`, { params: { ...(!snapshotId ? { merge_scale: view.mergeScale, split: view.split, policy_version: programme.policy_version } : {}), ...(filtered ? activeFilters : {}), format, filtered }, responseType: 'blob' })
      const url = URL.createObjectURL(data), anchor = document.createElement('a')
      anchor.href = url; anchor.download = `vaisala-programme-${surveyId}-${snapshotId || 'preview'}${filtered ? '-filtered' : ''}.${format}`
      anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (e) { if (mounted.current) setError(errorText(e)) }
    finally { if (mounted.current) setBusy('') }
  }
  const summary = programme?.summary || {}
  const total = programme?.total ?? summary.total_items ?? 0
  const filtered = programme?.filtered_total ?? total
  const items = programme?.items || []
  return <section aria-label="Action programme" style={{ marginBottom: 24 }}>
    <div className="card" style={{ padding: 20 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'start', justifyContent: 'space-between', gap: 16 }}>
        <div><h2 style={{ fontSize: 21, margin: '0 0 6px' }}>Action programme</h2>
          <p style={{ margin: 0, maxWidth: 730, lineHeight: 1.6 }}>A worklist of next decisions from this survey. Assessed coverage is not a construction quantity; no additional dataset or map is needed.</p></div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <select aria-label="Programme version" style={controlStyle} value={snapshotId} disabled={!!busy} onChange={e => { setSnapshotId(e.target.value); setSelected(null); setPage(1); setNotice(''); detailRequest.current += 1 }}>
            <option value="">Current preview (not saved)</option>
            {snapshots.map(s => <option key={s.id} value={String(s.id)}>Saved #{s.id} · {date(s.generated_at || s.created_at)} · {s.merge_scale || 'section'} / {s.split || 'combined'}</option>)}
          </select>
          {canEdit && <button className="btn btn-primary" onClick={saveProgramme} disabled={!!busy || loading || !programme || !!snapshotId}>{busy === 'save' ? 'Saving…' : 'Save programme'}</button>}
        </div>
      </div>
      <p style={{ color: 'var(--muted)', fontSize: 12 }}>Source: {survey?.source_filename || `Survey ${surveyId}`} · {snapshotId ? `Saved snapshot #${snapshotId}` : 'Live preview'} · Requested scale: {programme?.merge_scale || view.mergeScale} · Split: {programme?.split || view.split}. Urban extents use section scale. Unknown classifications remain visible.</p>
      {snapshotId && <p style={{ fontSize: 12 }}>Changing the source scale or split opens a fresh preview; saved reviews stay with this snapshot. Select “Current preview” to generate and save a new programme.</p>}
      {notice && <p role="status">{notice}</p>}
      {error && <div role="alert" style={{ color: 'var(--color-red, #b23a28)' }}>{error} <button style={controlStyle} onClick={() => setReload(n => n + 1)}>Retry loading</button></div>}
      {loading && <p role="status">Loading action programme…</p>}
      {programme && <>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 28, borderTop: '1px solid var(--color-border)', paddingTop: 16, marginTop: 16 }}>
          <span><strong>{summary.total_items ?? total}</strong> assessed records</span>
          <span><strong>{metres(summary.known_length_m)}</strong> known unique coverage</span>
          <span><strong>{summary.unresolved_extents ?? 0}</strong> unresolved extents</span>
        </div>
        <p style={{ fontSize: 12, color: 'var(--muted)' }}>Totals describe the whole programme. Queue coverage can overlap; overall unique coverage is calculated independently. Prerequisites do not add locations. Missing chainage is unresolved, not a nominal 10m length.</p>
        <VaisalaActionDiagnostics diagnostics={summary.action_diagnostics} />
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 16 }} aria-label="Action queues">
          <button style={{ ...controlStyle, borderWidth: filters.action === '' ? 2 : 1 }} aria-pressed={filters.action === ''} onClick={() => changeFilter('action', '')}>All actions ({total})</button>
          {Object.entries(ACTIONS).map(([code, label]) => <button key={code} aria-pressed={filters.action === code} onClick={() => changeFilter('action', code)} style={{ ...controlStyle, textAlign: 'left', maxWidth: 250, borderWidth: filters.action === code ? 2 : 1 }}>
            <strong style={{ display: 'block' }}>{label} ({(summary.current_action_counts || summary.action_counts)?.[code] || 0})</strong><span style={{ fontSize: 12 }}>{metres((summary.current_action_lengths_m || summary.action_lengths_m)?.[code] ?? 0)} assessed coverage</span>
          </button>)}
        </div>
        {filters.action && <p>{queueNotes[filters.action]}</p>}
        <p style={{ fontSize: 12, color: 'var(--muted)' }}>Queues include recorded client action changes. The model recommendation and original priority explanation remain available in each item; a changed client action receives no invented rank.</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, margin: '18px 0' }}>
          <label>Find location<br /><input aria-label="Find location" style={controlStyle} placeholder="Road or section reference" value={filters.search} onChange={e => changeFilter('search', e.target.value)} /></label>
          <label>Scale cohort<br /><select aria-label="Scale cohort" style={controlStyle} value={filters.scale} onChange={e => changeFilter('scale', e.target.value)}><option value="">All scale cohorts</option>{['section', '100m', '10m'].map(s => <option key={s}>{s}</option>)}</select></label>
          <label>RAG<br /><select aria-label="Programme RAG" style={controlStyle} value={filters.rag_band} onChange={e => changeFilter('rag_band', e.target.value)}><option value="">All RAG bands</option>{['Red', 'Amber', 'Green'].map(s => <option key={s}>{s}</option>)}</select></label>
          <label>Evidence<br /><select aria-label="Evidence status" style={controlStyle} value={filters.evidence_status} onChange={e => changeFilter('evidence_status', e.target.value)}><option value="">All evidence</option>{['adequate', 'limited', 'conflicting'].map(s => <option key={s}>{s}</option>)}</select></label>
          <label>Review<br /><select aria-label="Review filter" style={controlStyle} value={filters.review_status} onChange={e => changeFilter('review_status', e.target.value)}><option value="">All reviews</option>{STATUSES.map(s => <option key={s} value={s}>{displayValue(s)}</option>)}</select></label>
          <button style={{ ...controlStyle, alignSelf: 'end' }} onClick={() => { setFilters(emptyFilters); setPage(1); setSelected(null) }}>Clear filters</button>
        </div>
        <p style={{ fontSize: 12 }}>Showing {items.length ? (page - 1) * 50 + 1 : 0}–{Math.min(page * 50, filtered)} of {filtered} filtered records; {total} in the whole programme. Ranks are calculated before filters, separately by action and effective scale. Evidence validation uses validation order; unknown condition scores are unranked by condition.</p>
        <details style={{ marginBottom: 12 }}><summary>Effective-scale cohorts and rank denominators</summary><ul>{(programme.cohorts || []).map(c => <li key={`${c.assessment_scope}:${c.action}`}>{c.assessment_scope} · {ACTIONS[c.action]}: {c.total_items} records, {c.scored_items} scored; {metres(c.known_length_m)} known coverage, {c.unresolved_extents} unresolved extents.</li>)}</ul></details>
        <div style={{ overflowX: 'auto', opacity: loading ? 0.55 : 1 }} aria-busy={loading}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead><tr>{['Queue rank / order', 'Location / extent', 'Assessed length', 'Next action', 'Condition / RAG', 'Evidence', 'Next-step brief', 'Review'].map(label => <th key={label} style={{ padding: '10px 8px', textAlign: 'left', borderBottom: '2px solid var(--color-border)' }}>{label}</th>)}</tr></thead>
            <tbody>{items.map(item => <tr key={item.item_key} style={{ borderBottom: '1px solid var(--color-border)' }}>
              <td style={{ padding: 8 }}>{item.review?.client_action && item.review.client_action !== item.recommended_action ? 'Client decision · unranked' : item.recommended_action === 'evidence_validation' ? (item.validation_order == null ? 'Unordered' : `${item.validation_order} / ${item.queue_total ?? '—'}`) : item.queue_rank == null ? 'Unranked' : `${item.queue_rank} / ${item.queue_size ?? '—'}`}<small style={{ display: 'block' }}>{item.assessment_scope}{item.recommended_action === 'evidence_validation' && !item.review?.client_action ? ' · validation order' : ''}</small>{item.priority_score == null && <small>Condition score unknown</small>}</td>
              <td style={{ padding: 8 }}><button disabled={loading} onClick={() => openItem(item)} style={{ border: 0, padding: 0, background: 'none', color: 'var(--color-text)', cursor: 'pointer', textDecoration: 'underline', font: 'inherit', textAlign: 'left' }}>{item.section_ref || 'Unknown section'}</button><div>{item.road_name}</div><small>{item.chunk_label || 'Whole section'} · {displayValue(item.urban_rural)}</small></td>
              <td style={{ padding: 8 }}>{item.assessed_length_m == null && item.known_length_m > 0 ? `${metres(item.known_length_m)} known; remaining extent unresolved` : metres(item.assessed_length_m)}<small style={{ display: 'block' }}>{displayValue(item.length_basis)}</small></td>
              <td style={{ padding: 8 }}>{ACTIONS[item.effective_action || item.review?.client_action || item.recommended_action] || displayValue(item.recommended_action)}{item.review?.client_action && item.review.client_action !== item.recommended_action && <small style={{ display: 'block' }}>Model: {ACTIONS[item.recommended_action]}</small>}</td>
              <td style={{ padding: 8 }}>{item.priority_score == null ? 'Unknown score' : Number(item.priority_score).toFixed(2)}<strong style={{ display: 'block', color: ({ Red: '#b23a28', Amber: '#a66c13', Green: '#397650' })[item.rag_band] }}>{item.rag_band || 'Unknown RAG'}</strong></td>
              <td style={{ padding: 8 }}>{displayValue(item.evidence_status)}</td>
              <td style={{ padding: 8, minWidth: 180, maxWidth: 330 }}>{item.brief}</td>
              <td style={{ padding: 8 }}>{displayValue(item.review?.status || 'unreviewed')}{item.review?.client_action && <small style={{ display: 'block' }}>Client: {ACTIONS[item.review.client_action]}</small>}</td>
            </tr>)}</tbody>
          </table>
        </div>
        {!items.length && <p>{total ? 'No records match these filters. Clear filters to return to the full programme.' : 'This survey has no assessed programme records.'}</p>}
        <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginTop: 16 }}>
          <div style={{ display: 'flex', gap: 8 }}><button style={controlStyle} disabled={loading || page <= 1} onClick={() => { setPage(p => p - 1); setSelected(null) }}>Previous page</button><span style={{ padding: 8 }}>Page {page} of {Math.max(1, Math.ceil(filtered / 50))}</span><button style={controlStyle} disabled={loading || page * 50 >= filtered} onClick={() => { setPage(p => p + 1); setSelected(null) }}>Next page</button></div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}><button style={controlStyle} disabled={!!busy || loading} onClick={() => exportProgramme('xlsx', false)}>Export whole programme XLSX</button><button style={controlStyle} disabled={!!busy || loading} onClick={() => exportProgramme('csv', false)}>Export whole programme CSV</button><button style={controlStyle} disabled={!!busy || loading} onClick={() => exportProgramme('xlsx', true)}>Export filtered XLSX</button></div>
        </div>
        <p style={{ fontSize: 11, color: 'var(--muted)' }}>Model {programme.model_version} · Policy {programme.policy_version} · Generated {date(programme.generated_at)}. Survey date: {survey?.survey_date ? date(survey.survey_date) : 'unknown'}; imported {date(survey?.imported_at)}. {snapshotId ? 'Exports include this snapshot and recorded client reviews.' : 'Save a programme to freeze recommendations before client review.'}</p>
      </>}
    </div>
    {detailLoading && <p role="status">Loading item history…</p>}
    {selected && programme && <VaisalaProgrammeDetail key={`${snapshotId}:${selected.item_key}`} item={selected} programme={programme} canEdit={canEdit} onClose={() => { setSelected(null); detailRequest.current += 1; setDetailLoading(false) }} onReload={() => openItem(selected)} onReviewed={review => { setSelected(current => ({ ...current, review, review_history: [...(current.review_history || []), review] })); setReload(n => n + 1); setNotice('Review saved. Model recommendation remains unchanged.') }} />}
  </section>
}
