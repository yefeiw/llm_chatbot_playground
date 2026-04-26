# Week 3 Retrieval and Ranking Evolution

## Scope

This note summarizes the retrieval-quality work after the initial backend was stable. The focus moved from "can the assistant retrieve and answer?" to "can the answer, product cards, variants, and ranking all agree?"

Related earlier note:

- [Week 2 backend debugging summary](../week2/backend-debugging-summary.md)

## Starting Point

The MVP flow was:

1. Store the user message.
2. Embed the latest user message directly.
3. Retrieve top-k product documents from Qdrant.
4. Build a text context from retrieved product payloads.
5. Ask the LLM to answer from that context.
6. Return product cards from the same retrieved hits.

This worked for direct prompts such as:

```text
Find a lightweight suitcase with spinner wheels
```

But follow-ups and variant-heavy products exposed gaps.

## Problem 1: No Query Rewrite

Observed gap:

- A follow-up such as "show me cheaper ones" did not carry forward previous category/spec context.
- Retrieval embedded only the latest user message, so vague follow-ups could drift.

Implemented approach:

- Added `QueryRewriteService`.
- It rewrites the latest user turn into a standalone retrieval query using prior conversation.
- `/chat` uses the rewritten query for embedding and retrieval.
- Answer generation still sees the original user wording.
- If rewrite fails, the backend falls back to the original user message.

Why this shape:

- Query rewrite is a deterministic backend preprocessing step, not a model-chosen tool.
- Keeping it as an internal service makes the flow easier to test and debug.

Files:

- `backend/app/services/query_rewrite_service.py`
- `backend/app/api/chat.py`
- `backend/tests/test_query_rewrite_service.py`
- `backend/tests/test_chat_query_rewrite.py`

## Problem 2: ReAct Agent Demo

Question explored:

- Should query rewrite be represented as a tool in a ReAct-style agent?

Decision:

- The production path should keep rewrite as a normal backend service.
- A separate demo endpoint can show a ReAct-style loop for comparison.

Implemented demo:

- `POST /chat/react-demo`
- Action loop chooses among:
  - `rewrite_query`
  - `retrieve_products`
  - `finish`
- Returns a visible action trace through `agent_steps`.

Why it is demo-only:

- The production `/chat` path needs predictable retrieval behavior.
- The ReAct loop is useful for demos and teaching, but it adds planning variability.

Files:

- `backend/app/services/react_agent_service.py`
- `backend/app/api/chat.py`
- `backend/tests/test_react_agent_service.py`

## Problem 3: Answer and Product Card Variant Mismatch

Observed examples:

- `prod_0014` answer discussed the Gray leatherette chair variant, while the card showed the default Green mesh variant.
- `prod_0391` answer discussed the 32GB laptop variant, while the card showed the default 8GB variant.

Root cause:

- Retrieval was product-level.
- Product payloads flattened all variant specs into one list.
- The LLM could choose a later variant from the flat list.
- The frontend card rendered only `product.specs.slice(0, 5)`, which usually meant the first/default variant.

Implemented approach:

- Added `VariantSelectionService`.
- After product-level retrieval, the backend loads variants from SQLite.
- It selects one display variant per product using the rewritten query and category-specific heuristics.
- The selected variant replaces the product `specs` shown to the LLM and returned to the card.
- API responses now include `variant_uid` and `variant_name`.

Important behavior:

- The LLM and card now see the same selected variant.
- Stored retrieval logs include `selected_variant`.

Files:

- `backend/app/services/variant_selection_service.py`
- `backend/app/services/product_context_service.py`
- `backend/app/schemas/chat.py`
- `frontend/src/api/client.ts`
- `frontend/src/components/ChatWindow.tsx`
- `backend/tests/test_variant_selection_service.py`

## Problem 4: Answer Order and Card Order Diverged

Observed examples:

- For laptop recommendations, the card order had one product first, but the answer named a different product as the standout.
- The backend deterministic reranker and the LLM's implicit preference model disagreed.

First attempted fix:

- Added deterministic reranking before answer generation.
- Added explicit `rank` fields.
- Prompted the LLM not to reorder products and to name Rank 1 only as the top pick.

What improved:

- Product cards had visible rank.
- The prompt context included `Rank 1`, `Rank 2`, etc.
- Backend logs stored ranked results.

What still failed:

- The LLM sometimes ignored the ranking when the deterministic rank did not reflect the user-requested specs.
- Example: for "noise-canceling wireless headphones", deterministic rerank mostly rewarded generic category/rating, while the LLM preferred explicit `wireless: yes` and `noise_canceling: yes` matches.

Lesson:

- Ranking and evidence cannot be partially duplicated between backend and answer generation.
- The answer should not duplicate the product list at all.

Files from deterministic phase:

- `backend/app/services/result_rerank_service.py`
- `backend/tests/test_result_rerank_service.py`

## Current Contract: Cards Own Ranking, Answer Summarizes

Final design:

1. Query rewrite creates a standalone retrieval query.
2. Qdrant retrieves product-level candidates.
3. Variant selection chooses one variant per product.
4. LLM reranker ranks the enriched candidates and generates structured card evidence.
5. Backend validates the LLM ranking output.
6. Deterministic reranker is fallback if validation fails.
7. Product cards show rank, selected variant, evidence, caveats, and specs.
8. Final answer summarizes the ranked cards and tradeoffs, without listing products.

Why this is better:

- The card list is the source of truth for product order.
- The answer no longer tries to reproduce a product list and risk mismatched order.
- Evidence and caveats are structured and tied to each card.
- The LLM reranker can reason over explicit requested specs, while validation prevents invented evidence.

LLM reranker constraints:

- Must return JSON.
- Must rank only supplied `product_uid` values.
- Must include every candidate exactly once.
- Evidence must be copied exactly from allowed candidate evidence options.
- Caveats must be copied exactly from allowed candidate caveat options.
- Invalid output falls back to deterministic ranking.

Files:

- `backend/app/services/llm_rerank_service.py`
- `backend/app/services/result_rerank_service.py`
- `backend/app/services/product_context_service.py`
- `backend/app/services/llm_service.py`
- `backend/tests/test_llm_rerank_service.py`
- `backend/tests/test_product_context_service.py`

## Logging and Debugging

The backend now logs:

```text
Ranked results: [...]
Final answer: ...
```

`LLMEvent.prompt_snapshot_json` stores:

- `user_message`
- `retrieval_query`
- `query_rewritten`
- `reranked`
- `ranked_results`
- `answer`

This makes it possible to compare:

- retrieved candidates
- selected variants
- final rank order
- card evidence
- generated answer summary

Useful DB checks:

```bash
sqlite3 backend/shopping_assistant.db \
  "SELECT id, role, content, created_at FROM messages WHERE session_uid='SESSION_ID' ORDER BY id ASC;"
```

```bash
sqlite3 backend/shopping_assistant.db \
  "SELECT id, query_text, top_k, created_at FROM retrieval_events WHERE session_uid='SESSION_ID' ORDER BY id ASC;"
```

```bash
sqlite3 backend/shopping_assistant.db \
  "SELECT prompt_snapshot_json FROM llm_events WHERE session_uid='SESSION_ID' ORDER BY id DESC LIMIT 1;"
```

## Validation Added

Backend unit tests now cover:

- query rewrite prompt construction and fallback
- `/chat` rewrite/ranking orchestration
- variant selection for rain/carry and laptop examples
- product context rank/evidence formatting
- deterministic reranking fallback behavior
- validated LLM reranking
- ReAct demo action loop

Sanity checks used:

```bash
cd backend
OPENAI_API_KEY=test PYTHONPATH=. .venv/bin/python -m unittest discover -s tests
OPENAI_API_KEY=test PYTHONPATH=. .venv/bin/python -m compileall app tests

cd ../frontend
npm run build
```

Known warning:

- Backend tests still emit the existing SQLAlchemy `datetime.utcnow()` deprecation warning from model defaults.

## Remaining Gaps

1. Retrieval is still product-level, not variant-level.
2. The reranker sees only the top-k product candidates; if retrieval misses the right product, reranking cannot recover it.
3. Query rewrite is not scored by an eval set yet.
4. Structured filters for category, budget, price, and hard specs are still future work.
5. Product cards have evidence/caveats, but `Compare` and `Details` are still non-functional.
6. The ReAct endpoint is useful for demo purposes, but not the recommended production path.

## Design Principle Going Forward

Product cards should own product-specific detail and ordering.

The assistant answer should:

- summarize what the ranked cards optimize for
- call out broad tradeoffs
- avoid listing product names in a separate order
- avoid introducing product facts that are not already in card evidence/specs

