import { useEffect, useRef, useState } from 'react'
import { adminApi } from '../api/client'

const DATASET_NAMES = { scanner: 'SCANNER', cvi: 'CVI', scrim: 'SCRIM', reactive: 'Reactive', network: 'Network', vaisala: 'Vaisala', vaisala_network: 'Vaisala network' }

export function adminErrorMessage(error) {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) return detail.map(item => item.msg).join('. ')
  return typeof detail === 'string' ? detail : 'Unable to complete the request. Please try again.'
}

export function AdminDeleteDialog({ target, onClose, onDelete }) {
  const dialog = useRef(null)
  const [confirmation, setConfirmation] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const label = target.kind === 'user' ? target.user.email : target.kind === 'authority' ? target.authority.name
    : target.upload.source_file ?? 'Unattributed records'
  const title = target.kind === 'user' ? 'Delete user' : target.kind === 'authority' ? 'Delete authority' : 'Delete upload'
  useEffect(() => {
    const element = dialog.current
    element.showModal()
    return () => element.close()
  }, [])
  const submit = async event => {
    event.preventDefault()
    if (busy || confirmation !== label) return
    setBusy(true); setError('')
    try { await onDelete(target) }
    catch (err) { setError(adminErrorMessage(err)); setBusy(false) }
  }
  return <dialog ref={dialog} className="admin-modal" aria-labelledby="delete-title" aria-describedby="delete-description"
    onCancel={event => { event.preventDefault(); if (!busy) onClose() }}>
    <h2 id="delete-title">{title}</h2>
    <div id="delete-description" className="admin-delete-description">
      <p>Permanently delete <strong>{label}</strong>?</p>
      {target.kind === 'authority' && <p>All users and uploads must be removed first. Remaining derived analysis and empty asset records will also be removed.</p>}
      {target.kind === 'user' && <p>This user will lose access immediately. Their authority’s datasets will be retained.</p>}
      {target.kind === 'dataset' && <>
        <p><strong>{target.authority.authority_name}</strong> · {DATASET_NAMES[target.upload.dataset_type]} · {target.upload.record_count.toLocaleString()} stored records</p>
        <p>{target.upload.upload_id != null
          ? `Only upload #${target.upload.upload_id} and its associated records will be deleted.`
          : 'All retained records with this exact source filename in this dataset and authority will be deleted, including repeated imports with the same filename.'}</p>
        <p>Saved analysis for this authority will be cleared. Reactive totals will be rebuilt from remaining jobs where needed.</p>
      </>}
      <p>This cannot be undone.</p>
    </div>
    {error && <div className="alert alert-error" role="alert">{error}</div>}
    <form onSubmit={submit}>
      <fieldset disabled={busy}>
        <div className="form-group"><label htmlFor="delete-confirmation">Confirmation</label>
          <p className="admin-help" id="delete-confirmation-help">Type <strong>{label}</strong> to confirm.</p>
          <input autoFocus id="delete-confirmation" aria-describedby="delete-confirmation-help" value={confirmation} onChange={event => setConfirmation(event.target.value)} autoComplete="off" /></div>
        <div className="admin-modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn admin-btn-danger" disabled={confirmation !== label}>{busy ? 'Deleting…' : 'Delete permanently'}</button>
        </div>
      </fieldset>
    </form>
  </dialog>
}

export function AdminUploadList({ authority, onDelete }) {
  const [open, setOpen] = useState(false)
  const [uploads, setUploads] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const load = async () => {
    setLoading(true); setError('')
    try { const { data } = await adminApi.uploads(authority.authority_id); setUploads(data) }
    catch (err) { setError(adminErrorMessage(err)) }
    finally { setLoading(false) }
  }
  const toggle = () => { setOpen(!open); if (!open && uploads === null) load() }
  const id = `uploads-${authority.authority_id}`
  return <div className="admin-uploads">
    <button type="button" className="btn btn-secondary btn-sm" aria-expanded={open} aria-controls={id} onClick={toggle}>
      {open ? 'Hide uploads' : 'Manage uploads'}
    </button>
    {open && <div id={id}>
      <p className="admin-help">Vaisala uploads are listed individually. Other data is grouped by stored source filename; repeated imports with the same filename appear together.</p>
      {loading ? <p role="status" className="admin-empty">Loading uploads…</p> : error ? <div role="alert" className="alert alert-error">{error} <button className="btn btn-secondary btn-sm" onClick={load}>Retry</button></div>
        : <div className="card admin-table-wrap"><table className="data-table" aria-label={`Uploads for ${authority.authority_name}`}>
          <thead><tr><th scope="col">Dataset</th><th scope="col">Source file / survey</th><th scope="col">Stored records</th><th scope="col">Latest retained upload</th><th scope="col">Actions</th></tr></thead>
          <tbody>{uploads?.map(upload => <tr key={JSON.stringify([upload.dataset_type, upload.upload_id, upload.source_file])}>
            <td>{DATASET_NAMES[upload.dataset_type] ?? upload.dataset_type}</td>
            <td>{upload.source_file ?? 'Unattributed records'}<p className="admin-help">{upload.upload_id != null ? `Upload #${upload.upload_id}` : 'Source-file group'}</p></td>
            <td>{upload.record_count.toLocaleString()}</td>
            <td>{upload.uploaded_at ? new Date(upload.uploaded_at).toLocaleString('en-GB') : '—'}</td>
            <td><button type="button" className="btn btn-secondary btn-sm admin-delete-button" aria-label={`Delete ${upload.source_file ?? 'Unattributed records'}`}
              onClick={() => onDelete({ kind: 'dataset', authority, upload })}>Delete</button></td>
          </tr>)}{uploads?.length === 0 && <tr><td colSpan={5}>No retained uploads for this authority.</td></tr>}</tbody>
        </table></div>}
    </div>}
  </div>
}
