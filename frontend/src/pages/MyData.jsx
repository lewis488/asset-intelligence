import { useEffect, useState } from 'react'
import { assetsApi } from '../api/client'
import DatasetGrid from '../components/DatasetGrid'

export default function MyData() {
  const [data, setData]           = useState(null)
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const [selectedId, setSelectedId] = useState(null)

  useEffect(() => {
    assetsApi.myDatasets()
      .then(r => {
        const d = r.data
        setData(d)
        if (d.authorities?.length > 0) setSelectedId(d.authorities[0].authority_id)
      })
      .catch(() => setError('Failed to load dataset inventory'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div style={{ color: 'var(--color-text-dim)', padding: 40, fontFamily: 'var(--font-data)', fontSize: 13 }}>
      Loading…
    </div>
  )

  if (error) return (
    <div className="alert alert-error" style={{ marginTop: 0 }}>{error}</div>
  )

  const isAdmin = !!data?.authorities
  const selectedAuth = isAdmin ? data.authorities.find(a => a.authority_id === selectedId) : null
  const datasets = isAdmin ? selectedAuth?.datasets : data

  return (
    <div>
      <div className="page-header">
        <h1>My Data</h1>
        <p>Dataset inventory — records held for this authority</p>
      </div>

      {isAdmin && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
          <select
            value={selectedId ?? ''}
            onChange={e => setSelectedId(Number(e.target.value))}
            style={{
              background: 'var(--color-panel)',
              border: '1px solid var(--color-border-strong)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--color-text)',
              padding: '7px 12px',
              fontSize: 13,
              fontFamily: 'var(--font-ui)',
              cursor: 'pointer',
              minWidth: 220,
              outline: 'none',
            }}
          >
            {data.authorities.map(a => (
              <option key={a.authority_id} value={a.authority_id}>{a.authority_name}</option>
            ))}
          </select>
          <span style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>
            {data.total_authorities} {data.total_authorities === 1 ? 'authority' : 'authorities'} with data
          </span>
        </div>
      )}

      {datasets ? (
        <DatasetGrid datasets={datasets} />
      ) : (
        <div style={{ color: 'var(--color-text-dim)', fontSize: 13 }}>No data found.</div>
      )}
    </div>
  )
}
