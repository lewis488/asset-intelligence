import { useState } from 'react'
import { analysisApi } from '../api/client'
import ChatInterface from '../components/ChatInterface'

export default function Query() {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const send = async (text) => {
    const userMsg = { role: 'user', content: text }
    const next = [...messages, userMsg]
    setMessages(next); setLoading(true); setError('')
    try {
      const history = messages.map(m => ({ role: m.role, content: m.content }))
      const res = await analysisApi.query(text, history.length ? history : null)
      setMessages([...next, { role: 'assistant', content: res.data.answer }])
    } catch (err) {
      setError(err.response?.data?.detail || 'Query failed')
      setMessages(messages)
    } finally { setLoading(false) }
  }

  return (
    <div style={{ height: 'calc(100vh - 56px)', display: 'flex', flexDirection: 'column' }}>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', flexShrink: 0 }}>
        <div>
          <h1>Query</h1>
          <p>Ask Claude questions about your highway network — defect drivers, treatment priorities, reactive patterns</p>
        </div>
        {messages.length > 0 && (
          <button className="btn btn-secondary btn-sm" onClick={() => { setMessages([]); setError('') }}>Clear</button>
        )}
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <ChatInterface messages={messages} onSend={send} loading={loading} />
      </div>
    </div>
  )
}
