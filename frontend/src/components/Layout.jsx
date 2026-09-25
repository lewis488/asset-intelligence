import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const Ic = {
  dashboard: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
      <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
    </svg>
  ),
  upload: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
    </svg>
  ),
  analysis: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
    </svg>
  ),
  query: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
  ),
  vaisala: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="6" cy="19" r="3"/>
      <path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/>
      <circle cx="18" cy="5" r="3"/>
    </svg>
  ),
  myData: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3"/>
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
    </svg>
  ),
  admin: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7l-9-4Z"/>
      <path d="m8 12 3 3 5-6"/>
    </svg>
  ),
  signOut: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
      <polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
    </svg>
  ),
}

const NAV = [
  { to: '/dashboard', label: 'Dashboard',   icon: Ic.dashboard, key: 'dashboard' },
  { to: '/upload',    label: 'Upload Data', icon: Ic.upload,    key: 'upload' },
  { to: '/analysis',  label: 'Analysis',    icon: Ic.analysis,  key: 'analysis' },
  { to: '/query',     label: 'Query',       icon: Ic.query,     key: 'query' },
  { to: '/vaisala',   label: 'Vaisala DST', icon: Ic.vaisala,   key: 'vaisala' },
  { to: '/my-data',   label: 'My Data',     icon: Ic.myData,    key: 'my-data' },
  { to: '/admin',     label: 'Admin',       icon: Ic.admin,     adminOnly: true },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const initials = user?.email ? user.email.slice(0, 2).toUpperCase() : '??'

  return (
    <div className="app-layout">
      <header className="topnav">
        {/* Logo */}
        <div className="topnav-logo">
          <span className="topnav-logo-dot" />
          <span className="topnav-logo-name">Asset Intelligence</span>
          <span className="topnav-logo-sub">Highway Network Mgmt</span>
        </div>

        {/* Nav tabs */}
        <nav className="topnav-nav">
          {NAV.filter(item => {
            if (item.adminOnly) return user?.role === 'admin'
            if (!item.key) return true
            const modules = user?.enabled_modules
            return !modules || modules.includes(item.key)
          }).map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              aria-label={label}
              className={({ isActive }) =>
                `topnav-link${isActive ? ' topnav-link--active' : ''}`
              }
            >
              {icon}
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User + sign out */}
        <div className="topnav-end">
          <div className="topnav-avatar">{initials}</div>
          <span className="topnav-email">{user?.email}</span>
          <button
            className="topnav-signout"
            onClick={() => { logout(); navigate('/login') }}
          >
            {Ic.signOut}
            Sign out
          </button>
        </div>
      </header>

      <main className="main-content"><Outlet /></main>
    </div>
  )
}
