# Shopping Assistant Project Overview

## Goal

Build a product-only shopping assistant that can retrieve relevant catalog items, answer grounded recommendation questions, and present product results in a useful shopping UI.

The current project is a local MVP. It uses mock products, OpenAI embeddings/response generation, local Qdrant retrieval, SQLite session memory, and a React/Vite frontend.

## Current Architecture

Request flow:

1. The user sends a message from the React chat UI.
2. `POST /chat` stores the user message in SQLite.
3. The backend embeds the latest user message with OpenAI embeddings.
4. Qdrant returns the top semantic product matches.
5. The backend builds product context from retrieved payloads.
6. OpenAI generates a grounded answer using conversation history plus retrieved products.
7. The API returns the answer and structured product cards to the frontend.
8. The frontend renders the assistant response with image-led product cards.

Core files:

- `backend/app/api/chat.py`: main chat endpoint and orchestration.
- `backend/app/data/mock_catalog_generator.py`: deterministic mock catalog generation.
- `backend/app/services/ingestion_service.py`: writes mock products to SQLite and Qdrant.
- `backend/app/services/retrieval_service.py`: process-wide Qdrant client and vector search wrapper.
- `backend/app/services/llm_service.py`: OpenAI response generation.
- `frontend/src/components/ChatWindow.tsx`: main shopping assistant UI.
- `frontend/src/components/ChatWindow.css`: visual system and product-card styling.
- `scripts/dev.sh`: starts and monitors frontend/backend together.
- `scripts/seed.sh`: reseeds SQLite and Qdrant from the repo root.

## Current Status

Working:

- Local FastAPI backend with `/chat`, `/health`, and debug endpoints.
- OpenAI embeddings and answer generation.
- Local Qdrant vector store for product retrieval.
- SQLite persistence for sessions, messages, retrieval events, and LLM events.
- Mock catalog with 1,500 products across 15 categories.
- Category-level generated SVG product illustrations.
- Structured product response fields: title, brand, category, description, price, image URL, product URL, rating, review count, score, and specs.
- React shopping UI with prompt chips, message bubbles, product cards, prices, images, specs, and lightweight actions.
- Dev helper scripts for seeding and running both apps.

Recent product categories:

- headphones
- laptops
- monitors
- keyboards
- mice
- blenders
- coffee makers
- vacuums
- backpacks
- suitcases
- smartwatches
- tablets
- speakers
- air fryers
- desk chairs

## Known Gaps

The biggest retrieval gap is follow-up intent handling. A prompt like "show me cheaper ones" does not currently rewrite the query or carry over the previous category/filter context before retrieval. The next implementation step should be query rewriting/contextual retrieval so the second turn becomes something like "cheaper lightweight suitcases with spinner wheels" before vector search.

Other gaps:

- Retrieval is basic top-k semantic search, without structured filters for category, price, rating, inventory, or variant constraints.
- Product images are category illustrations, not unique per-product images.
- Product URLs are placeholders, not real product detail pages.
- The UI has non-functional `Compare` and `Details` buttons.
- There are no automated backend, frontend, or retrieval-quality tests yet.
- The catalog is mock data, not a real merchant or Amazon feed.
- Qdrant uses local file-backed storage, so only one process should access `backend/qdrant_data` at a time.

## Recommended Next Steps

1. **Query rewriting and contextual retrieval**
   - Detect vague follow-ups such as "cheaper ones", "lighter options", and "compare the top two".
   - Rewrite retrieval queries using recent conversation and previous retrieval categories.
   - Add structured filters for carried-over category and price constraints.

2. **Comparison and details UX**
   - Make `Compare` and `Details` buttons functional.
   - Add side-by-side comparison tables for top products.
   - Show why each product matched the user request.

3. **Retrieval quality evaluation**
   - Add a small eval set with expected categories and key constraints.
   - Track whether retrieved products satisfy category/spec/price requirements.
   - Run the eval before changing retrieval logic.

4. **Catalog realism**
   - Add product-detail pages for mock products.
   - Generate per-product images if the mock catalog remains synthetic.
   - If using real products later, integrate a legitimate product feed/API rather than scraping Amazon.

5. **Operational cleanup**
   - Keep seeding separate from normal server startup.
   - Consider a Qdrant server if concurrent access becomes necessary.
   - Add tests and CI once the retrieval contract stabilizes.

## Daily Commands

Seed or reseed the mock catalog:

```bash
./scripts/seed.sh
```

Start frontend and backend together:

```bash
./scripts/dev.sh
```

Stop the dev stack:

```text
Ctrl-C
```

Run current sanity checks:

```bash
cd backend
python -m compileall app seed.py

cd ../frontend
npm run build
```
