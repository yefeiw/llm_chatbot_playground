import { useState } from 'react'
import { sendMessage } from '../api/client'

type Turn = { role: 'user' | 'assistant'; text: string }

export function ChatWindow() {
  const [sessionId] = useState(() => `sess_${crypto.randomUUID().slice(0, 8)}`)
  const [input, setInput] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [loading, setLoading] = useState(false)

  const onSend = async () => {
    if (!input.trim() || loading) return
    const text = input.trim()
    setInput('')
    setTurns((t) => [...t, { role: 'user', text }])
    setLoading(true)
    try {
      const res = await sendMessage(sessionId, text)
      setTurns((t) => [...t, { role: 'assistant', text: `${res.answer}\n\nRetrieved: ${res.retrieved_products.join(', ')}` }])
    } catch (e) {
      setTurns((t) => [...t, { role: 'assistant', text: `Error: ${(e as Error).message}` }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: 20, fontFamily: 'Inter, Arial' }}>
      <h2>LLM Shopping Assistant</h2>
      <p>Session: <code>{sessionId}</code></p>
      <div style={{ border: '1px solid #ddd', borderRadius: 8, minHeight: 360, padding: 12, marginBottom: 12 }}>
        {turns.map((t, idx) => (
          <div key={idx} style={{ marginBottom: 10 }}>
            <strong>{t.role === 'user' ? 'You' : 'Assistant'}:</strong>
            <div style={{ whiteSpace: 'pre-wrap' }}>{t.text}</div>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask for product recommendations..."
          style={{ flex: 1, padding: 10 }}
          onKeyDown={(e) => e.key === 'Enter' && onSend()}
        />
        <button onClick={onSend} disabled={loading}>
          {loading ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  )
}
