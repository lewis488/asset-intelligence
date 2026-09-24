import { useEffect, useRef, useState } from 'react'
import api from '../api/client'
import VaisalaTreatmentAssessment from './VaisalaTreatmentAssessment'

export const ACTIONS = {
  engineer_assessment: 'Engineer assessment',
  evidence_validation: 'Validate evidence / further survey',
  treatment_appraisal: 'Treatment appraisal',
  monitor: 'Monitor observed deterioration',
  no_action_indicated: 'No intervention indicated by this survey',
}
export const STATUSES = ['unreviewed', 'accepted', 'assigned', 'completed', 'deferred']
export const controlStyle = { padding: '7px 9px', border: '1px solid var(--color-border)', borderRadius: 5, background: 'var(--color-surface)', color: 'var(--color-text)', font: 'inherit' }
export const displayValue = value => value == null || value === '' ? 'Unknown' : String(value).replaceAll('_', ' ')
export function errorText(error) {
  const detail = error.response?.data?.detail
  return typeof detail === 'string' ? detail : 'The request could not be completed. Please try again.'
}

export default function VaisalaProgrammeDetail({ item, programme, canEdit, onClose, onReviewed, onReload }) {
  const [status, setStatus] = useState('unreviewed')
  const [clientAction, setClientAction] = useState('')
  const [comment, setComment] = useState('')
  const [assignee, setAssignee] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [conflict, setConflict] = useState(false)
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => {
    setStatus(item.review?.status || 'unreviewed')
    setClientAction(item.review?.client_action || '')
    setComment(item.review?.comment || '')
    setAssignee(item.review?.assignee || '')
    setError(''); setConflict(false)
  }, [item.item_key, item.review?.sequence])
  const reasonRequired = status === 'deferred' || clientAction !== (item.review?.client_action || '')
  async function saveReview(event) {
    event.preventDefault()
    setBusy(true); setError(''); setConflict(false)
    try {
      const { data } = await api.post(`/vaisala/programmes/${programme.id}/items/${encodeURIComponent(item.item_key)}/reviews`, {
        expected_sequence: item.review?.sequence || 0, status, client_action: clientAction || null, comment, assignee,
      })
      if (mounted.current) onReviewed(data)
    } catch (e) {
      if (!mounted.current) return
      setConflict(e.response?.status === 409)
      setError(e.response?.status === 409 ? 'Another reviewer changed this item. Your inputs are retained. Load the latest review before submitting again.' : errorText(e))
    } finally { if (mounted.current) setBusy(false) }
  }
  return <section aria-label="Programme item detail" className="card" style={{ padding: 22, marginTop: 18 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
      <div><h3 style={{ margin: '0 0 6px' }}>{item.section_ref || 'Unknown section'}{item.road_name ? ` — ${item.road_name}` : ''}</h3>
        <p style={{ margin: 0, color: 'var(--muted)' }}>{item.chunk_label || 'Whole section'} · {item.assessment_scope || 'Unknown scale'} · {displayValue(item.urban_rural)} classification</p></div>
      <button style={controlStyle} onClick={onClose}>Close item</button>
    </div>
    <h4>Model recommendation: {ACTIONS[item.recommended_action] || displayValue(item.recommended_action)}</h4>
    <p style={{ maxWidth: 850, lineHeight: 1.7 }}>{item.brief}</p>
    <p><strong>Question to resolve:</strong> {item.next_question || 'Review the evidence and confirm the next decision.'}</p>
    <p><strong>Original model queue:</strong> {item.priority_explanation}</p>
    <p style={{ fontSize: 12 }}>Survey-and-scale condition percentile: {item.priority_percentile == null ? 'Unknown / unranked' : Number(item.priority_percentile).toFixed(1)} · {item.priority_cohort_size ?? 'Unknown'} scored records in the {item.assessment_scope || 'unknown'} cohort. This is independent of the current queue and filters.</p>
    {!!item.prerequisite_tasks?.length && <><strong>Additional prerequisite tasks</strong><ul>{item.prerequisite_tasks.map((task, i) => <li key={i}>{typeof task === 'string' ? displayValue(task) : task.brief || task.label || task.description || JSON.stringify(task)}</li>)}</ul></>}
    <VaisalaTreatmentAssessment assessment={item.treatment_assessment} scope={item.assessment_scope} percentile={item.priority_percentile} showAction={false} />
    <details style={{ marginTop: 14 }}><summary>Source and method</summary>
      <dl style={{ lineHeight: 1.8 }}>
        <dt>Item key</dt><dd style={{ overflowWrap: 'anywhere' }}>{item.item_key}</dd>
        <dt>Source survey</dt><dd>{programme.survey_id}; survey date: {displayValue(item.survey_date)}. Import date: {displayValue(programme.imported_at)}.</dd>
        <dt>Source references</dt><dd>Section: {displayValue(item.section_ref)}; network reference: {displayValue(item.net_reference)}; parent section ID: {displayValue(item.parent_section_id)}.</dd>
        <dt>Source intervals</dt><dd>{item.source_interval_ids?.length ? item.source_interval_ids.join(', ') : 'Not supplied'}; chainage {displayValue(item.from_m)} to {displayValue(item.to_m)} m.</dd>
        <dt>Survey QC</dt><dd>Completeness: {item.qc_completeness_pct == null ? 'Unknown' : `${Number(item.qc_completeness_pct).toFixed(1)}%`}; reliability: {item.qc_reliability_pct == null ? 'Unknown' : `${Number(item.qc_reliability_pct).toFixed(1)}%`}.</dd>
        <dt>Assessment generated</dt><dd>{displayValue(programme.generated_at)}</dd>
        <dt>Model / policy</dt><dd>{displayValue(programme.model_version)} / {displayValue(programme.policy_version)}</dd>
        <dt>Assessed length basis</dt><dd>{displayValue(item.length_basis)}. These are assessed lengths, not repair quantities.</dd>
        <dt>Reference linkage</dt><dd>Section and network references are supplied identifiers; a section reference alone does not confirm an NSG link.</dd>
      </dl>
    </details>
    <div style={{ borderTop: '1px solid var(--color-border)', marginTop: 20, paddingTop: 14 }}>
      <h4 style={{ marginTop: 0 }}>Client review</h4>
      <p>Current status: <strong>{displayValue(item.review?.status || 'unreviewed')}</strong>. Client action: <strong>{ACTIONS[item.review?.client_action] || 'No separate client action'}</strong>.</p>
      <p style={{ color: 'var(--muted)', fontSize: 12 }}>A client decision retains the model recommendation. Completion records workflow progress, not proof of repaired condition. An assignee label sends no notification.</p>
      {!programme.id && <p>Save programme to record reviews against a fixed snapshot.</p>}
      {!canEdit && <p>Read-only access: reviews can be viewed and exported.</p>}
      {canEdit && programme.id && <form onSubmit={saveReview}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14 }}>
          <label>Review status<br /><select aria-label="Review status" value={status} onChange={e => setStatus(e.target.value)} style={controlStyle}>{STATUSES.map(s => <option key={s} value={s}>{displayValue(s)}</option>)}</select></label>
          <label>Client action<br /><select aria-label="Client action" value={clientAction} onChange={e => setClientAction(e.target.value)} style={controlStyle}><option value="">Retain model recommendation</option>{Object.entries(ACTIONS).map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label>
          <label>Assignee label{status === 'assigned' ? ' (required)' : ''}<br /><input aria-label="Assignee label" maxLength={200} style={controlStyle} value={assignee} onChange={e => setAssignee(e.target.value)} required={status === 'assigned'} /></label>
        </div>
        <label style={{ display: 'block', marginTop: 14 }}>Review comment{reasonRequired ? ' (reason required)' : ''}<br /><textarea aria-label="Review comment" maxLength={5000} rows={3} style={{ ...controlStyle, width: '100%', boxSizing: 'border-box' }} value={comment} onChange={e => setComment(e.target.value)} required={reasonRequired} /></label>
        {error && <p role="alert" style={{ color: 'var(--color-red, #b23a28)' }}>{error}</p>}
        {conflict && <button type="button" style={controlStyle} onClick={async () => { if (await onReload()) { setConflict(false); setError('') } }}>Load latest review</button>}
        <button type="submit" className="btn btn-primary" style={{ marginTop: 10 }} disabled={busy || conflict || (reasonRequired && !comment.trim()) || (status === 'assigned' && !assignee.trim())}>{busy ? 'Saving review…' : 'Save review'}</button>
      </form>}
      <details style={{ marginTop: 16 }}><summary>Review history ({item.review_history?.length || (item.review?.sequence ? 1 : 0)})</summary>
        {(item.review_history || (item.review?.sequence ? [item.review] : [])).map(review => <div key={review.sequence} style={{ marginTop: 10, borderBottom: '1px solid var(--color-border)', paddingBottom: 8 }}>
          <strong>{displayValue(review.status)}</strong> · {review.reviewer_name || `Reviewer ${review.reviewer_id || 'unknown'}`} · {displayValue(review.created_at)}
          {review.client_action && <p>Client action: {ACTIONS[review.client_action]}</p>}{review.assignee && <p>Assigned to: {review.assignee}</p>}{review.comment && <p>{review.comment}</p>}
        </div>)}
        {!item.review?.sequence && !item.review_history?.length && <p>No reviews recorded.</p>}
      </details>
    </div>
  </section>
}
