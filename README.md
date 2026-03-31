# LLM Shopping Assistant (FastAPI + OpenAI + Qdrant)

A product-only shopping assistant with:
- FastAPI backend
- OpenAI API for embeddings + response generation
- Qdrant local vector store for embedding-based retrieval
- SQLite for session memory and structured event logging
- React/Vite UI chat client

## What it does
- Seeds 1,000 mock products across multiple categories.
- Embeds product docs and stores vectors in local Qdrant.
- Answers chat queries using top-k semantic retrieval.
- Persists full conversation history in DB per session.
- Exposes debugging endpoints for retrieval and prompt snapshots.

## Backend setup

```bash
cp .env.example .env
# fill OPENAI_API_KEY
./scripts/run_backend.sh
```

Backend starts at `http://localhost:8000`.

## Frontend setup

```bash
./scripts/run_frontend.sh
```

UI starts at `http://localhost:5173`.

Set `VITE_API_BASE` if backend is not on localhost:8000.

## API

### Chat
`POST /chat`

```json
{
  "session_id": "sess_123",
  "message": "Recommend a lightweight suitcase with spinner wheels"
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
