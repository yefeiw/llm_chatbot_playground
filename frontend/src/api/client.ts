export type ProductResult = {
  product_uid: string
  title: string
  brand: string
  category: string
  description: string
  price_cents: number | null
  image_url: string | null
  product_url: string | null
  rating: number | null
  review_count: number | null
  score: number | null
  specs: string[]
}

export type ChatResponse = {
  session_id: string
  answer: string
  products: ProductResult[]
}

const defaultApiBase = `http://${window.location.hostname || 'localhost'}:8000`
const API_BASE = import.meta.env.VITE_API_BASE ?? defaultApiBase

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
