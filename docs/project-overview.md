# Shopping Assistant Project Overview

## Goal

Build a product-only shopping assistant that can retrieve relevant catalog items, answer grounded recommendation questions, and present product results in a useful shopping UI.

The current project is a local MVP. It uses mock products, OpenAI embeddings/response generation, local Qdrant retrieval, SQLite session memory, and a React/Vite frontend.

## Current Architecture

Request flow:

1. The user sends a message from the React chat UI.
2. `POST /chat` stores the user message in SQLite.
3. The backend rewrites the latest user message into a standalone retrieval query using prior conversation context.
4. The backend embeds the rewritten query with OpenAI embeddings.
5. Qdrant returns the top semantic product matches.
6. The backend selects one display variant per product.
7. The backend uses validated LLM reranking to order products and generate card evidence, with deterministic fallback.
8. The backend builds product context from selected variants in ranked order.
9. OpenAI generates a grounded summary using conversation history plus ranked card evidence.
10. The API returns the answer and structured product cards in the same ranked order.
11. The frontend renders the assistant response with image-led product cards.

Core files:

- `backend/app/api/chat.py`: main chat endpoint and orchestration.
- `backend/app/data/mock_catalog_generator.py`: deterministic mock catalog generation.
- `backend/app/services/ingestion_service.py`: writes mock products to SQLite and Qdrant.
- `backend/app/services/product_context_service.py`: builds the product context shown to the LLM.
- `backend/app/services/query_rewrite_service.py`: rewrites follow-up turns into standalone retrieval queries.
- `backend/app/services/llm_rerank_service.py`: ranks enriched product hits and generates validated card evidence.
- `backend/app/services/result_rerank_service.py`: deterministic fallback reranker.
- `backend/app/services/variant_selection_service.py`: selects one product variant for the answer and card.
- `backend/app/services/react_agent_service.py`: demo ReAct-style action loop around rewrite, retrieval, and answer tools.
- `backend/app/services/retrieval_service.py`: process-wide Qdrant client and vector search wrapper.
- `backend/app/services/llm_service.py`: OpenAI response generation.
- `frontend/src/components/ChatWindow.tsx`: main shopping assistant UI.
- `frontend/src/components/ChatWindow.css`: visual system and product-card styling.
- `scripts/dev.sh`: starts and monitors frontend/backend together.
- `scripts/seed.sh`: reseeds SQLite and Qdrant from the repo root.

## Current Status

Working:

- Local FastAPI backend with `/chat`, `/health`, and debug endpoints.
- Demo `POST /chat/react-demo` endpoint that returns a visible action trace for a ReAct-style agent loop.
- LLM-based query rewriting before vector retrieval, with fallback to the original user message.
- Variant-aware product cards so the answer context and displayed specs use the same selected variant.
- Validated LLM reranking before answer generation so card order, evidence, and caveats come from one structured ranking step.
- OpenAI embeddings and answer generation.
- Local Qdrant vector store for product retrieval.
- SQLite persistence for sessions, messages, retrieval events, and LLM events.
- Mock catalog with 1,500 products across 15 categories.
- Category-level generated SVG product illustrations.
- Structured product response fields: rank, title, brand, category, description, selected variant, price, image URL, product URL, rating, review count, score, evidence, caveats, summary, and specs.
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

Retrieval now handles basic follow-up query rewriting, but it is still unstructured. The next retrieval-quality gap is turning inferred constraints into explicit filters and measurable evals.

- Retrieval is basic top-k semantic search, without structured filters for category, price, rating, inventory, or variant constraints.
- Query rewriting is LLM-based and covered by unit tests, but not yet scored against a retrieval-quality eval set.
- Product images are category illustrations, not unique per-product images.
- Product URLs are placeholders, not real product detail pages.
- The UI has non-functional `Compare` and `Details` buttons.
- There are focused backend tests for query rewrite, variant selection, reranking, eval graders, and the ReAct demo loop, plus a local retrieval/ranking eval harness under `backend/evals/`.
- The catalog is mock data, not a real merchant or Amazon feed.
- Qdrant uses local file-backed storage, so only one process should access `backend/qdrant_data` at a time.

## Recommended Next Steps

1. **Structured contextual retrieval**
   - Extract carried-over category, price, rating, and spec constraints alongside the rewritten query.
   - Apply structured filters after or during vector retrieval.
   - Log enough metadata to explain why a product matched.

2. **Comparison and details UX**
   - Make `Compare` and `Details` buttons functional.
   - Add side-by-side comparison tables for top products.
   - Show why each product matched the user request.

3. **Retrieval quality evaluation**
   - Use [`evaluation-plan.md`](evaluation-plan.md) as the working plan.
   - Expand the initial eval set with more expected categories and key constraints.
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
PYTHONPATH=. python evals/run_eval.py

cd ../frontend
npm run build
```
