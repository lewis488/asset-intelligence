import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { authApi } from '../api/client'

export default function Login() {
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const set = e => setForm({ ...form, [e.target.name]: e.target.value })

  const submit = async e => {
    e.preventDefault(); setError(''); setLoading(true)
    try {
      const res = await authApi.login(form.email, form.password)
      login(res.data.access_token, res.data.user)
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Something went wrong')
    } finally { setLoading(false) }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Asset Intelligence</h1>
        <p className="subtitle">Sign in to your authority account</p>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={submit}>
          <div className="form-group"><label htmlFor="login-email">Email</label>
            <input id="login-email" type="email" name="email" value={form.email} onChange={set} placeholder="you@authority.gov.uk" autoComplete="username" required /></div>
          <div className="form-group"><label htmlFor="login-password">Password</label>
            <input id="login-password" type="password" name="password" value={form.password} onChange={set} placeholder="••••••••" autoComplete="current-password" required minLength={8} /></div>
          <button type="submit" className="btn btn-primary" style={{ width: '100%', justifyContent: 'center', marginTop: 4 }} disabled={loading}>
            {loading ? <span className="spinner" /> : 'Sign In'}
          </button>
        </form>
        <p className="admin-help" style={{ marginTop: 16, textAlign: 'center' }}>Need access? Contact your administrator.</p>
      </div>
    </div>
  )
}
