import { useCallback, useEffect, useRef, useState } from 'react'
import { adminApi } from '../api/client'
import { useAuth } from '../context/AuthContext'
import DatasetGrid from '../components/DatasetGrid'
import { AdminDeleteDialog, AdminUploadList, adminErrorMessage as errorMessage } from '../components/AdminDeletion'
import '../styles/admin.css'

const TABS = ['Authorities', 'Users', 'Data Overview']

function AdminModal({ kind, editedUser, authorities, onClose, onSave }) {
  const dialog = useRef(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [form, setForm] = useState({
    name: '', region: '', email: editedUser?.email ?? '', password: '',
    authority_id: editedUser?.authority_id ?? '', role: editedUser?.role ?? 'viewer',
    is_active: editedUser?.is_active ?? true,
  })
  const isAuthority = kind === 'authority'
  const title = isAuthority ? 'New authority' : editedUser ? 'Edit user' : 'New user'
  useEffect(() => {
    const element = dialog.current
    element.showModal()
    return () => element.close()
  }, [])
  const change = event => setForm(previous => ({
    ...previous, [event.target.name]: event.target.type === 'checkbox' ? event.target.checked : event.target.value,
  }))
  const submit = async event => {
    event.preventDefault()
    if (saving) return
    setError('')
    if (isAuthority && !form.name.trim()) { setError('Enter an authority name.'); return }
    if (!isAuthority && !editedUser && new TextEncoder().encode(form.password).length > 72) {
      setError('Password must be at most 72 UTF-8 bytes.'); return
    }
    setSaving(true)
    try {
      if (isAuthority) {
        const { data } = await adminApi.createAuthority({ name: form.name.trim(), region: form.region.trim() || null })
        onSave('authority', data)
      } else {
        const fields = { authority_id: Number(form.authority_id), role: form.role }
        const { data } = editedUser
          ? await adminApi.updateUser(editedUser.id, { ...fields, is_active: form.is_active })
          : await adminApi.createUser({ ...fields, email: form.email.trim(), password: form.password })
        onSave('user', data)
      }
    } catch (err) { setError(errorMessage(err)); setSaving(false) }
  }
  return (
    <dialog ref={dialog} className="admin-modal" aria-labelledby="admin-modal-title"
      onCancel={event => { event.preventDefault(); if (!saving) onClose() }}>
      <div className="admin-toolbar">
        <h2 id="admin-modal-title">{title}</h2>
        <button type="button" className="btn btn-secondary btn-sm" aria-label="Close dialog" disabled={saving} onClick={onClose}>×</button>
      </div>
      {error && <div className="alert alert-error" role="alert">{error}</div>}
      <form onSubmit={submit}>
        <fieldset disabled={saving}>
          {isAuthority ? <>
            <div className="form-group"><label htmlFor="authority-name">Authority name</label>
              <input autoFocus id="authority-name" name="name" value={form.name} onChange={change} required maxLength={255} /></div>
            <div className="form-group"><label htmlFor="authority-region">Region</label>
              <input id="authority-region" name="region" value={form.region} onChange={change} maxLength={255} /></div>
          </> : <>
            <div className="form-group"><label htmlFor="user-email">Email</label>
              <input autoFocus id="user-email" name="email" type="email" value={form.email} onChange={change} required readOnly={!!editedUser} autoComplete="off" /></div>
            {!editedUser && <div className="form-group"><label htmlFor="user-password">Password</label>
              <input id="user-password" name="password" type="password" value={form.password} onChange={change} required minLength={8} maxLength={72} autoComplete="new-password" />
              <p className="admin-help">At least 8 characters.</p></div>}
            <div className="form-group"><label htmlFor="user-authority">Authority</label>
              <select id="user-authority" name="authority_id" value={form.authority_id} onChange={change} required>
                <option value="" disabled>Select an authority</option>
                {authorities.map(authority => <option key={authority.id} value={authority.id}>{authority.name}</option>)}
              </select></div>
            <div className="form-group"><label htmlFor="user-role">Role</label>
              <select id="user-role" name="role" value={form.role} onChange={change}>
                {['viewer', 'manager', 'admin'].map(role => <option key={role} value={role}>{role}</option>)}
              </select></div>
            {editedUser && <label className="admin-checkbox"><input name="is_active" type="checkbox" checked={form.is_active} onChange={change} />Active</label>}
          </>}
          <div className="admin-modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary" type="submit">{saving ? 'Saving…' : isAuthority ? 'Create authority' : editedUser ? 'Save changes' : 'Create user'}</button>
          </div>
        </fieldset>
      </form>
    </dialog>
  )
}

function PasswordResetModal({ targetUser, onClose, onSaved }) {
  const dialog = useRef(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  useEffect(() => {
    const element = dialog.current
    element.showModal()
    return () => element.close()
  }, [])
  const submit = async event => {
    event.preventDefault()
    if (saving) return
    setError('')
    if (newPassword !== confirmPassword) { setError('Passwords do not match.'); return }
    if (new TextEncoder().encode(newPassword).length > 72) { setError('Password must be at most 72 UTF-8 bytes.'); return }
    setSaving(true)
    try {
      await adminApi.resetUserPassword(targetUser.id, newPassword)
      onSaved()
    } catch (err) { setError(errorMessage(err)); setSaving(false) }
  }
  return (
    <dialog ref={dialog} className="admin-modal" aria-labelledby="pwd-reset-title"
      onCancel={event => { event.preventDefault(); if (!saving) onClose() }}>
      <div className="admin-toolbar">
        <h2 id="pwd-reset-title">Reset password</h2>
        <button type="button" className="btn btn-secondary btn-sm" aria-label="Close dialog" disabled={saving} onClick={onClose}>×</button>
      </div>
      <p className="admin-help">Setting new password for <strong>{targetUser.email}</strong>.</p>
      {error && <div className="alert alert-error" role="alert">{error}</div>}
      <form onSubmit={submit}>
        <fieldset disabled={saving}>
          <div className="form-group"><label htmlFor="new-password">New password</label>
            <input autoFocus id="new-password" type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} required minLength={8} maxLength={72} autoComplete="new-password" />
            <p className="admin-help">At least 8 characters.</p></div>
          <div className="form-group"><label htmlFor="confirm-password">Confirm password</label>
            <input id="confirm-password" type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} required minLength={8} maxLength={72} autoComplete="new-password" /></div>
          <div className="admin-modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary" type="submit">{saving ? 'Saving…' : 'Reset password'}</button>
          </div>
        </fieldset>
      </form>
    </dialog>
  )
}

export default function Admin() {
  const { user, token, login, logout } = useAuth()
  const [tab, setTab] = useState('Authorities')
  const [inventory, setInventory] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [modal, setModal] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [passwordResetTarget, setPasswordResetTarget] = useState(null)
  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [authorities, users, overview] = await Promise.all([
        adminApi.authorities(), adminApi.users(), adminApi.dataOverview(),
      ])
      setInventory({ authorities: authorities.data, users: users.data, overview: overview.data.authorities })
    } catch (err) { setError(errorMessage(err)) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { load() }, [load])

  const deleteItem = async target => {
    if (target.kind === 'user') await adminApi.deleteUser(target.user.id)
    else if (target.kind === 'authority') await adminApi.deleteAuthority(target.authority.id)
    else await adminApi.deleteUpload(target.authority.authority_id, target.upload.dataset_type,
      target.upload.upload_id != null ? { upload_id: target.upload.upload_id } : { source_file: target.upload.source_file })
    setDeleteTarget(null)
    setNotice(target.kind === 'user' ? 'User deleted.' : target.kind === 'authority' ? 'Authority deleted.' : 'Upload deleted. Saved analysis cleared.')
    await load()
  }

  const saved = (kind, item) => {
    setModal(null)
    if (kind === 'user' && item.id === user.id) {
      if (!item.is_active) { logout(); return }
      login(token, item)
      if (item.role !== 'admin') return
    }
    setInventory(previous => {
      if (kind === 'authority') return {
        ...previous,
        authorities: [...previous.authorities, item].sort((a, b) => a.name.localeCompare(b.name)),
        overview: [...previous.overview, { authority_id: item.id, authority_name: item.name, datasets: {} }],
      }
      return { ...previous, users: previous.users.some(entry => entry.id === item.id)
        ? previous.users.map(entry => entry.id === item.id ? item : entry)
        : [...previous.users, item] }
    })
    setNotice(kind === 'authority' ? 'Authority created.' : 'User saved.')
  }

  const selectTab = next => { setTab(next); setNotice('') }
  const tabKeyDown = event => {
    const index = TABS.indexOf(tab)
    const next = event.key === 'ArrowRight' ? (index + 1) % TABS.length
      : event.key === 'ArrowLeft' ? (index + TABS.length - 1) % TABS.length
      : event.key === 'Home' ? 0 : event.key === 'End' ? TABS.length - 1 : null
    if (next === null) return
    event.preventDefault(); selectTab(TABS[next])
    document.getElementById(`admin-tab-${next}`).focus()
  }
  const authorities = inventory?.authorities ?? []
  const users = inventory?.users ?? []
  const overview = inventory?.overview ?? []
  const authorityNames = new Map(authorities.map(authority => [authority.id, authority.name]))
  const userCounts = new Map()
  users.forEach(entry => userCounts.set(entry.authority_id, (userCounts.get(entry.authority_id) ?? 0) + 1))
  const datasetCounts = new Map(overview.map(authority => [authority.authority_id,
    Object.values(authority.datasets).filter(dataset => dataset.record_count > 0).length]))

  return (
    <div className="admin-page">
      <div className="page-header"><h1>Admin</h1><p>Manage authorities, user access and uploaded data.</p></div>
      <div className="admin-tabs" role="tablist" aria-label="Admin sections" onKeyDown={tabKeyDown}>
        {TABS.map((label, index) => <button key={label} id={`admin-tab-${index}`} type="button" role="tab"
          aria-selected={tab === label} aria-controls="admin-panel" tabIndex={tab === label ? 0 : -1}
          onClick={() => selectTab(label)}>{label}</button>)}
      </div>
      <div id="admin-panel" role="tabpanel" aria-labelledby={`admin-tab-${TABS.indexOf(tab)}`} aria-busy={loading}>
        {notice && <div className="alert alert-success" role="status">{notice}</div>}
        {loading ? <p className="admin-empty" role="status">Loading admin data…</p>
          : error ? <div className="alert alert-error" role="alert">{error} <button className="btn btn-secondary btn-sm" onClick={load}>Retry</button></div>
          : <>
            <div className="admin-toolbar">
              <div><h2>{tab}</h2><p className="admin-help">{tab === 'Authorities' ? 'Dataset count is the number of dataset types with stored records.'
                : tab === 'Users' ? 'Assign each user an authority and an access role.'
                  : 'Stored records and latest upload dates, grouped by authority.'}</p></div>
              {tab === 'Authorities' && <button className="btn btn-primary" onClick={() => setModal({ kind: 'authority' })}>+ New Authority</button>}
              {tab === 'Users' && <button className="btn btn-primary" disabled={!authorities.length} onClick={() => setModal({ kind: 'user' })}>+ New User</button>}
            </div>
            {tab === 'Authorities' && <div className="card admin-table-wrap"><table className="data-table" aria-label="Authorities">
              <thead><tr><th scope="col">Name</th><th scope="col">Region</th><th scope="col">User count</th><th scope="col">Dataset count</th><th scope="col">Actions</th></tr></thead>
              <tbody>{authorities.map(authority => <tr key={authority.id}>
                <td>{authority.name}</td><td>{authority.region || '—'}</td>
                <td>{userCounts.get(authority.id) ?? 0}</td><td>{datasetCounts.get(authority.id) ?? 0}</td>
                <td><button type="button" className="btn btn-secondary btn-sm admin-delete-button" aria-label={`Delete ${authority.name}`} onClick={() => setDeleteTarget({ kind: 'authority', authority })}>Delete</button></td>
              </tr>)}{!authorities.length && <tr><td colSpan={5}>No authorities yet. Create an authority to get started.</td></tr>}</tbody>
            </table></div>}
            {tab === 'Users' && <>
              {!authorities.length && <p className="admin-empty">Create an authority in the Authorities tab before adding users.</p>}
              <div className="card admin-table-wrap"><table className="data-table" aria-label="Users">
                <thead><tr><th scope="col">Email</th><th scope="col">Authority</th><th scope="col">Role</th><th scope="col">Active</th><th scope="col">Actions</th></tr></thead>
                <tbody>{users.map(entry => <tr key={entry.id}>
                  <td>{entry.email}</td><td>{authorityNames.get(entry.authority_id) ?? `Authority ${entry.authority_id}`}</td>
                  <td>{entry.role}</td><td><span className={`badge ${entry.is_active ? 'badge-Green' : 'badge-Unknown'}`}>{entry.is_active ? 'Active' : 'Inactive'}</span></td>
                  <td><div className="admin-row-actions"><button className="btn btn-secondary btn-sm" aria-label={`Edit ${entry.email}`} onClick={() => setModal({ kind: 'user', editedUser: entry })}>Edit</button>
                    <button className="btn btn-secondary btn-sm" aria-label={`Reset password for ${entry.email}`} onClick={() => setPasswordResetTarget(entry)}>Reset password</button>
                    <button type="button" className="btn btn-secondary btn-sm admin-delete-button" aria-label={`Delete ${entry.email}`} disabled={entry.id === user.id} title={entry.id === user.id ? 'You cannot delete your own account' : undefined} onClick={() => setDeleteTarget({ kind: 'user', user: entry })}>Delete</button></div></td>
                </tr>)}{!users.length && <tr><td colSpan={5}>No users yet. Add a user to grant access.</td></tr>}</tbody>
              </table></div>
            </>}
            {tab === 'Data Overview' && (overview.length ? overview.map(authority => <section className="admin-authority" key={authority.authority_id} aria-labelledby={`authority-${authority.authority_id}`}>
              <h3 id={`authority-${authority.authority_id}`}>{authority.authority_name}</h3>
              <DatasetGrid datasets={authority.datasets} overview />
              <AdminUploadList authority={authority} onDelete={setDeleteTarget} />
            </section>) : <p className="admin-empty">No authorities yet. Create an authority to get started.</p>)}
          </>}
      </div>
      {modal && <AdminModal {...modal} authorities={authorities} onClose={() => setModal(null)} onSave={saved} />}
      {passwordResetTarget && <PasswordResetModal targetUser={passwordResetTarget} onClose={() => setPasswordResetTarget(null)} onSaved={() => { setPasswordResetTarget(null); setNotice('Password updated.') }} />}
      {deleteTarget && <AdminDeleteDialog target={deleteTarget} onClose={() => setDeleteTarget(null)} onDelete={deleteItem} />}
    </div>
  )
}
