import { createContext, useContext, useState, useEffect } from 'react'

const AuthContext = createContext(null)

const AUTO_EMAIL = 'lewis@sunshinecorner.co.uk'
const AUTO_PASSWORD = 'Highway2026!'

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('ai_token'))
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('ai_user')) } catch { return null }
  })
  const [ready, setReady] = useState(() => !!localStorage.getItem('ai_token'))

  useEffect(() => {
    if (token) { setReady(true); return }
    const params = new URLSearchParams()
    params.append('username', AUTO_EMAIL)
    params.append('password', AUTO_PASSWORD)
    fetch('http://localhost:8000/auth/login', { method: 'POST', body: params })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.access_token) {
          const u = { email: AUTO_EMAIL }
          localStorage.setItem('ai_token', data.access_token)
          localStorage.setItem('ai_user', JSON.stringify(u))
          setToken(data.access_token)
          setUser(u)
        }
      })
      .catch(() => {})
      .finally(() => setReady(true))
  }, [])

  const login = (t, u) => {
    localStorage.setItem('ai_token', t)
    localStorage.setItem('ai_user', JSON.stringify(u))
    setToken(t); setUser(u)
  }

  const logout = () => {
    localStorage.removeItem('ai_token')
    localStorage.removeItem('ai_user')
    setToken(null); setUser(null)
  }

  if (!ready) return null

  return (
    <AuthContext.Provider value={{ token, user, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
