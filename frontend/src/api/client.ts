export type ChatResponse = {
  session_id: string
  answer: string
  retrieved_products: string[]
}

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export async function sendMessage(sessionId: string, message: string): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message })
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || 'Failed to chat')
  }

  return res.json()
}
