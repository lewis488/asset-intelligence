import { useEffect, useRef, useState } from 'react'

const PROMPTS = [
  'Which B+C road sections have the highest LPV contribution — structural concern?',
  'Are there any A road roundabouts in the critical band?',
  'Show assets where high reactive spend suggests planned intervention would be more cost-effective',
  'What parishes have the highest concentration of high-risk assets?',
  'Which sections would be suitable for surface dressing rather than structural treatment?',
]

export default function ChatInterface({ messages, onSend, loading }) {
  const [text, setText] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])

  const submit = () => {
    const q = text.trim()
    if (!q || loading) return
    setText('')
    onSend(q)
  }

  return (
    <div className="chat-wrap">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', padding: '32px 20px' }}>
            <div style={{ fontSize: 32, marginBottom: 10 }}>💬</div>
            <p style={{ color: 'var(--muted)', marginBottom: 18, fontSize: 13.5 }}>Ask Claude anything about your loaded network data</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, justifyContent: 'center' }}>
              {PROMPTS.map(p => (
                <button key={p} onClick={() => onSend(p)}
                  style={{ padding: '6px 12px', border: '1px solid var(--border)', borderRadius: 18, background: '#fff', cursor: 'pointer', fontSize: 12, color: 'var(--muted)' }}>
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg ${m.role}`}>
            <div className="chat-bubble">{m.content}</div>
          </div>
        ))}
        {loading && (
          <div className="chat-msg assistant">
            <div className="chat-bubble" style={{ display: 'flex', gap: 8, alignItems: 'center', color: 'var(--muted)' }}>
              <span className="spinner" style={{ width: 15, height: 15 }} /> Claude is analysing…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="chat-input-row">
        <textarea value={text} onChange={e => setText(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
          placeholder="Ask about your network data… (Enter to send)"
          rows={2} disabled={loading} />
        <button className="btn btn-primary" onClick={submit} disabled={!text.trim() || loading} style={{ alignSelf: 'flex-end' }}>
          Send
        </button>
      </div>
    </div>
  )
}
