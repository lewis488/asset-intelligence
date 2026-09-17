import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { authApi } from '../api/client'

export default function Login() {
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ email: '', password: '', authority_name: '', region: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const set = e => setForm({ ...form, [e.target.name]: e.target.value })

  const submit = async e => {
    e.preventDefault(); setError(''); setLoading(true)
    try {
      if (mode === 'register') {
        await authApi.register({ email: form.email, password: form.password, authority_name: form.authority_name, region: form.region })
        setMode('login')
      } else {
        const res = await authApi.login(form.email, form.password)
        login(res.data.access_token, res.data.user)
        navigate('/dashboard')
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Something went wrong')
    } finally { setLoading(false) }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Asset Intelligence</h1>
        <p className="subtitle">{mode === 'login' ? 'Sign in to your authority account' : 'Register your authority'}</p>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={submit}>
          {mode === 'register' && <>
            <div className="form-group"><label>Authority Name</label>
              <input name="authority_name" value={form.authority_name} onChange={set} placeholder="e.g. West Sussex County Council" required /></div>
            <div className="form-group"><label>Region</label>
              <input name="region" value={form.region} onChange={set} placeholder="e.g. South East" /></div>
          </>}
          <div className="form-group"><label>Email</label>
            <input type="email" name="email" value={form.email} onChange={set} placeholder="you@authority.gov.uk" required /></div>
          <div className="form-group"><label>Password</label>
            <input type="password" name="password" value={form.password} onChange={set} placeholder="••••••••" required minLength={8} /></div>
          <button type="submit" className="btn btn-primary" style={{ width: '100%', justifyContent: 'center', marginTop: 4 }} disabled={loading}>
            {loading ? <span className="spinner" /> : mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>
        <div className="login-toggle">
          {mode === 'login'
            ? <>No account? <button onClick={() => setMode('register')}>Register your authority</button></>
            : <>Already registered? <button onClick={() => setMode('login')}>Sign in</button></>}
        </div>
      </div>
    </div>
  )
}
