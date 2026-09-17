import { useEffect, useState } from 'react'
import { analysisApi } from '../api/client'
import AIBriefing from '../components/AIBriefing'
import PriorityList from '../components/PriorityList'
import DefectDriverChart from '../components/DefectDriverChart'

export default function Analysis() {
  const [run, setRun] = useState(null)
  const [running, setRunning] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    analysisApi.latest()
      .then(r => setRun(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const doRun = async () => {
    setRunning(true); setError('')
    try { setRun((await analysisApi.run()).data) }
    catch (err) { setError(err.response?.data?.detail || 'Analysis failed') }
    finally { setRunning(false) }
  }

  // Extract top asset with scanner data for chart
  const topWithScanner = run?.priority_list_json?.find(a => a.scanner_data?.ci_contribution_lpv != null)

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div><h1>AI Analysis</h1><p>Claude-powered briefing using UKPMS engineering knowledge base</p></div>
        <button className="btn btn-primary" onClick={doRun} disabled={running}>
          {running ? <><span className="spinner" /> Analysing…</> : '▶ Run New Analysis'}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {loading && <div style={{ textAlign: 'center', padding: 40 }}><span className="spinner" /></div>}

      {!loading && !run && !error && (
        <div className="card" style={{ textAlign: 'center', padding: 48 }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🧠</div>
          <h3 style={{ fontWeight: 600, marginBottom: 8 }}>No analysis yet</h3>
          <p style={{ color: 'var(--muted)', marginBottom: 20 }}>Upload SCANNER or CVI data then run an analysis</p>
          <button className="btn btn-primary" onClick={doRun} disabled={running}>Run Analysis</button>
        </div>
      )}

      {run && (
        <>
          <AIBriefing summaryText={run.summary_text} createdAt={run.created_at} />

          {topWithScanner && (
            <div className="card" style={{ marginTop: 16 }}>
              <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>Top Priority Asset — Defect Driver Breakdown</h2>
              <p style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 12 }}>
                {topWithScanner.nsg_ref} — {topWithScanner.road_name || 'Unknown road'} ({topWithScanner.parish || '—'})
              </p>
              <DefectDriverChart scannerData={topWithScanner.scanner_data}
                title={`CI contributions — ${topWithScanner.dominant_defect_driver || 'mixed'} driver`} />
            </div>
          )}

          {run.priority_list_json?.length > 0 && (
            <div className="card" style={{ marginTop: 16 }}>
              <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Priority List (from this analysis run)</h2>
              <PriorityList assets={run.priority_list_json} loading={false} />
            </div>
          )}
        </>
      )}
    </div>
  )
}
