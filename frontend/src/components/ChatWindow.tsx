import { useState } from 'react'
import { ProductResult, sendMessage } from '../api/client'
import './ChatWindow.css'

type Turn = {
  role: 'user' | 'assistant'
  text: string
  products?: ProductResult[]
}

const QUICK_PROMPTS = [
  'Find a lightweight suitcase with spinner wheels',
  'Compare comfortable desk chairs under $300',
  'Recommend noise-canceling wireless headphones',
  'Show me waterproof speakers with long battery life',
]

function createSessionId() {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return `sess_${globalThis.crypto.randomUUID().slice(0, 8)}`
  }

  if (typeof globalThis.crypto?.getRandomValues === 'function') {
    const bytes = globalThis.crypto.getRandomValues(new Uint8Array(4))
    const randomPart = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
    return `sess_${randomPart}`
  }

  return `sess_${Math.random().toString(16).slice(2, 10)}`
}

export function ChatWindow() {
  const [sessionId] = useState(createSessionId)
  const [input, setInput] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [loading, setLoading] = useState(false)

  const onSend = async (message = input) => {
    if (!message.trim() || loading) return
    const text = message.trim()
    setInput('')
    setTurns((t) => [...t, { role: 'user', text }])
    setLoading(true)
    try {
      const res = await sendMessage(sessionId, text)
      setTurns((t) => [...t, { role: 'assistant', text: res.answer, products: res.products }])
    } catch (e) {
      setTurns((t) => [...t, { role: 'assistant', text: `Error: ${(e as Error).message}` }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="shopping-shell">
      <section className="shopping-hero">
        <div>
          <p className="eyebrow">AI shopping desk</p>
          <h1>Find the right product without tab-hopping.</h1>
          <p className="hero-copy">
            Ask for tradeoffs, compare recommendations, and refine by specs like weight, battery life, capacity, and comfort.
          </p>
        </div>
        <div className="session-card">
          <span>Session</span>
          <code>{sessionId}</code>
        </div>
      </section>

      <section className="prompt-rail" aria-label="Suggested prompts">
        {QUICK_PROMPTS.map((prompt) => (
          <button key={prompt} className="prompt-pill" onClick={() => onSend(prompt)} disabled={loading}>
            {prompt}
          </button>
        ))}
      </section>

      <section className="chat-panel" aria-label="Shopping conversation">
        {turns.length === 0 ? (
          <div className="empty-state">
            <span>Start with a constraint</span>
            <p>Try asking for a specific budget, feature, or use case. Product cards will appear with prices, specs, and images.</p>
          </div>
        ) : (
          turns.map((t, idx) => (
            <div key={idx} className={`turn turn-${t.role}`}>
              <div className="turn-label">{t.role === 'user' ? 'You' : 'Assistant'}</div>
              <div className="turn-bubble">
                <div className="turn-text">{t.text}</div>
                {t.products && t.products.length > 0 && (
                  <div className="product-grid">
                    {t.products.map((product) => (
                      <ProductCard key={product.product_uid} product={product} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </section>

      <div className="composer">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask for product recommendations..."
          onKeyDown={(e) => e.key === 'Enter' && onSend()}
        />
        <button onClick={() => onSend()} disabled={loading}>
          {loading ? 'Searching...' : 'Send'}
        </button>
      </div>
    </main>
  )
}

function ProductCard({ product }: { product: ProductResult }) {
  const score =
    typeof product.score === 'number' ? `${Math.max(0, Math.min(100, Math.round(product.score * 100)))}% match` : 'Recommended'
  const price = typeof product.price_cents === 'number' ? `$${(product.price_cents / 100).toFixed(2)}` : 'Price unavailable'
  const imageUrl = product.image_url || `/product-images/categories/${product.category}.svg`
  const category = product.category.replaceAll('_', ' ')

  return (
    <article className="product-card">
      <div className="product-image-wrap">
        <img src={imageUrl} alt="" className="product-image" loading="lazy" />
        {product.rank && <span className="rank-badge">#{product.rank}</span>}
        <span className="match-badge">{score}</span>
      </div>
      <div className="product-body">
        <div className="product-kicker">
          <span>{product.brand}</span>
          <span>{product.rank ? `#${product.rank} ${category}` : category}</span>
        </div>
        <h3>{product.title}</h3>
        {product.variant_name && <div className="variant-label">{product.variant_name}</div>}
        <p>{product.description}</p>
        {product.rank_summary && <p className="rank-summary">{product.rank_summary}</p>}
        <div className="product-meta">
          <strong>{price}</strong>
          <span>{product.rating ?? 'N/A'} rating</span>
          <span>{product.review_count?.toLocaleString() ?? 'N/A'} reviews</span>
        </div>
        {product.evidence.length > 0 && (
          <div className="evidence-list" aria-label="Ranking evidence">
            {product.evidence.slice(0, 4).map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        )}
        {product.caveats.length > 0 && (
          <div className="caveat-list" aria-label="Ranking caveats">
            {product.caveats.slice(0, 2).map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        )}
        <div className="spec-list">
          {product.specs.slice(0, 5).map((spec) => (
            <span key={spec}>{spec}</span>
          ))}
        </div>
        <div className="product-actions">
          <button type="button">Compare</button>
          <button type="button" className="secondary-action">Details</button>
        </div>
      </div>
    </article>
  )
}
