# LLM Shopping Assistant (FastAPI + OpenAI + Qdrant)

A product-only shopping assistant with:
- FastAPI backend
- OpenAI API for embeddings + response generation
- Qdrant local vector store for embedding-based retrieval
- SQLite for session memory and structured event logging
- React/Vite UI chat client

See [docs/project-overview.md](docs/project-overview.md) for architecture, current status, known gaps, and next steps.

## What it does
- Seeds 1,500 mock products across 15 categories.
- Adds generated local product illustrations, prices, specs, ratings, and review counts.
- Embeds product docs and stores vectors in local Qdrant.
- Answers chat queries using query-rewritten retrieval, variant selection, and validated LLM reranking with deterministic fallback.
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
      "rank": 1,
      "product_uid": "prod_0419",
      "title": "Aster Suitcases Model 0419",
      "brand": "Aster",
      "category": "suitcases",
      "description": "Reliable suitcases for everyday use with balanced performance.",
      "variant_uid": "var_0419_0",
      "variant_name": "Option 1",
      "price_cents": 12900,
      "image_url": "/product-images/categories/suitcases.svg",
      "product_url": "/products/prod_0419",
      "rating": 4.7,
      "review_count": 2301,
      "score": 0.78,
      "evidence": ["spinner_wheels: yes", "weight_kg: 1.82"],
      "caveats": [],
      "rank_summary": "Best match for lightweight spinner-wheel criteria.",
      "specs": ["color: Blue", "weight_kg: 1.82", "spinner_wheels: yes"]
    }
  ]
}
```

### ReAct Demo Chat
`POST /chat/react-demo`

Accepts the same request body as `/chat`, but runs a demo ReAct-style loop that chooses internal actions such as `rewrite_query`, `retrieve_products`, and `finish`. The response includes the normal answer and product cards plus `retrieval_query` and `agent_steps` for debugging/demo visibility.

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
- Follow-up query rewriting runs before retrieval, so short relative prompts like "show me cheaper ones" can carry prior shopping context into vector search.
- The backend selects one variant per product and uses validated LLM reranking to generate card order, evidence, and caveats. The answer summarizes the ranked cards instead of duplicating the product list.
