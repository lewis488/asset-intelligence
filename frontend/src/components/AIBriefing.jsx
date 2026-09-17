export default function AIBriefing({ summaryText, createdAt }) {
  const date = createdAt
    ? new Date(createdAt).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    : null

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h2 style={{ fontSize: 15, fontWeight: 600 }}>AI Management Briefing</h2>
          {date && <p style={{ color: 'var(--muted)', fontSize: 12, marginTop: 2 }}>Generated {date}</p>}
        </div>
        <div style={{ background: '#eff6ff', color: '#3b82f6', padding: '3px 10px', borderRadius: 99, fontSize: 11.5, fontWeight: 600 }}>
          Claude
        </div>
      </div>
      <p className="briefing-body">{summaryText}</p>
    </div>
  )
}
