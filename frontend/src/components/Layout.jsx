import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

// ── Inline SVG icons (Tabler-style, 18×18) ───────────────────────────────────
const Ic = {
  dashboard: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
      <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
    </svg>
  ),
  upload: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="17 8 12 3 7 8"/>
      <line x1="12" y1="3" x2="12" y2="15"/>
    </svg>
  ),
  analysis: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
    </svg>
  ),
  query: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
  ),
  vaisala: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="6" cy="19" r="3"/>
      <path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/>
      <circle cx="18" cy="5" r="3"/>
    </svg>
  ),
  chevronLeft: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="15 18 9 12 15 6"/>
    </svg>
  ),
  chevronRight: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 18 15 12 9 6"/>
    </svg>
  ),
  myData: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3"/>
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
    </svg>
  ),
  signOut: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
      <polyline points="16 17 21 12 16 7"/>
      <line x1="21" y1="12" x2="9" y2="12"/>
    </svg>
  ),
}

const NAV = [
  { to: '/dashboard', label: 'Dashboard',   icon: Ic.dashboard },
  { to: '/upload',    label: 'Upload Data', icon: Ic.upload },
  { to: '/analysis',  label: 'Analysis',    icon: Ic.analysis },
  { to: '/query',     label: 'Query',       icon: Ic.query },
  { to: '/vaisala',   label: 'Vaisala DST', icon: Ic.vaisala },
  { to: '/my-data',   label: 'My Data',     icon: Ic.myData  },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(() =>
    localStorage.getItem('sidebar_collapsed') === 'true'
  )

  const toggleCollapsed = () => {
    setCollapsed(v => {
      const next = !v
      localStorage.setItem('sidebar_collapsed', String(next))
      return next
    })
  }

  const initials = user?.email ? user.email.slice(0, 2).toUpperCase() : '??'

  return (
    <div className="app-layout">
      <aside className={`sidebar${collapsed ? ' sidebar--collapsed' : ''}`}>

        {/* Logo */}
        <div className="sidebar-logo">
          <div style={{ display: 'flex', alignItems: 'center', gap: collapsed ? 0 : 8 }}>
            <span style={{
              width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
              background: 'var(--color-amber)',
              boxShadow: '0 0 7px var(--color-amber)',
            }} />
            {!collapsed && (
              <span style={{ color: '#F9FAFB', fontSize: 14, fontWeight: 500, whiteSpace: 'nowrap', marginLeft: 2 }}>
                Asset Intelligence
              </span>
            )}
          </div>
          {!collapsed && (
            <div style={{ color: 'var(--color-text-muted)', fontSize: 11, marginTop: 5 }}>
              Highway Network Mgmt
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="sidebar-nav">
          {NAV.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                `sidebar-link${isActive ? ' sidebar-link--active' : ''}`
              }
            >
              <span className="sidebar-link-icon">{icon}</span>
              {!collapsed && <span className="sidebar-link-label">{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="sidebar-footer">
          {/* Avatar */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: collapsed ? 0 : 8,
            marginBottom: 10,
            justifyContent: collapsed ? 'center' : 'flex-start',
          }}>
            <div style={{
              width: 28, height: 28, borderRadius: '50%',
              background: 'var(--color-amber)',
              color: '#000',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, fontWeight: 700, flexShrink: 0,
            }}>{initials}</div>
            {!collapsed && (
              <span style={{
                fontSize: 12, color: 'var(--color-text-muted)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {user?.email}
              </span>
            )}
          </div>

          {/* Collapse toggle */}
          <button className="sidebar-collapse-btn" onClick={toggleCollapsed}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
            {collapsed ? Ic.chevronRight : Ic.chevronLeft}
          </button>

          {/* Sign out */}
          <button
            className={`sidebar-signout-btn${collapsed ? ' sidebar-signout-btn--icon' : ''}`}
            onClick={() => { logout(); navigate('/login') }}
            title={collapsed ? 'Sign out' : undefined}
          >
            {Ic.signOut}
            {!collapsed && <span>Sign out</span>}
          </button>
        </div>

      </aside>
      <main className="main-content"><Outlet /></main>
    </div>
  )
}
