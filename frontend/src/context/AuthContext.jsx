import { createContext, useContext, useState } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('ai_token'))
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('ai_user')) } catch { return null }
  })

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

  return (
    <AuthContext.Provider value={{ token, user, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
