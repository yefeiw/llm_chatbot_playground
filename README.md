# LLM Shopping Assistant (FastAPI + OpenAI + Qdrant)

A product-only shopping assistant with:
- FastAPI backend
- OpenAI API for embeddings + response generation
- Qdrant local vector store for embedding-based retrieval
- SQLite for session memory and structured event logging
- React/Vite UI chat client

## What it does
- Seeds 1,500 mock products across 15 categories.
- Adds generated local product illustrations, prices, specs, ratings, and review counts.
- Embeds product docs and stores vectors in local Qdrant.
- Answers chat queries using top-k semantic retrieval.
- Persists full conversation history in DB per session.
- Exposes debugging endpoints for retrieval and prompt snapshots.

## One-Time Setup

Backend:

```bash
python -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
# fill OPENAI_API_KEY in .env
./scripts/seed.sh
```

Frontend:

```bash
cd frontend
npm install
```

## Development

After dependencies are installed, `backend/.env` exists, and the catalog has been seeded, start both apps with:

```bash
./scripts/dev.sh
```

The dev supervisor starts:

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`

It waits for both apps to become reachable and stops both processes if either one exits.

Set `VITE_API_BASE` if backend is not on localhost:8000.

## API

### Chat
`POST /chat`

Request:

```json
{
  "session_id": "sess_123",
  "message": "Recommend a lightweight suitcase with spinner wheels"
}
```

Response:

```json
{
  "session_id": "sess_123",
  "answer": "A concise recommendation based on the retrieved products.",
  "products": [
    {
      "product_uid": "prod_0419",
      "title": "Aster Suitcases Model 0419",
      "brand": "Aster",
      "category": "suitcases",
      "description": "Reliable suitcases for everyday use with balanced performance.",
      "price_cents": 12900,
      "image_url": "/product-images/categories/suitcases.svg",
      "product_url": "/products/prod_0419",
      "rating": 4.7,
      "review_count": 2301,
      "score": 0.78,
      "specs": ["color: Blue", "weight_kg: 1.82", "spinner_wheels: yes"]
    }
  ]
}
```

### Debug
- `GET /debug/session/{session_id}`
- `GET /debug/retrieval?session_id=...`
- `GET /debug/prompts/{session_id}`
- `GET /debug/logs/{session_id}`
- `GET /debug/retrieve?query=...&top_k=8`
- `POST /debug/reindex`

## Notes
- This is intentionally product-only: no pricing/deals/shipping/offers.
- The app uses complete session history as memory for each turn.
- Follow-up query rewriting is a known next step. Short relative prompts like "show me cheaper ones" currently need explicit context handling before retrieval.
