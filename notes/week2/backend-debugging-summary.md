# Week 2 Backend Debugging Summary

## Scope

This note summarizes the debugging session around bringing the `llm_chatbot_playground` backend up, validating OpenAI API access, fixing retrieval failures, and verifying the main chat flow end to end.

## Initial blockers

### 1. OpenAI API key existed, but API calls failed

Observed behavior:

- `OPENAI_API_KEY` was present in the shell environment.
- The backend failed during `python seed.py`.
- The OpenAI API returned `429 insufficient_quota`.

What we verified:

- `GET /v1/models` succeeded, proving the key itself was valid.
- `POST /v1/embeddings` failed with `429 insufficient_quota`.
- `POST /v1/responses` also failed with `429 insufficient_quota`.

Conclusion:

- This was not a missing-key problem.
- It was an API billing/quota problem on the specific API org/project attached to the key.
- ChatGPT Plus billing was not relevant to API quota.

Resolution:

- After funding the API account/project, both embeddings and response generation started returning `200`.

## Backend startup behavior

### 2. `run_backend.sh` was slow because it reseeded the full catalog

Observed behavior:

- `scripts/run_backend.sh` recreates the virtualenv, installs requirements, runs `python seed.py`, and only then starts uvicorn.
- Seeding 1,000 products takes time because it creates embeddings for the catalog.

Operational learning:

- A backend process is not "booted" until uvicorn prints its startup line.
- Before that, `seed.py` may still be running, even though the shell looks busy for a while.

## Retrieval bugs found

### 3. Qdrant client API mismatch

Observed error:

```text
AttributeError: 'QdrantClient' object has no attribute 'search'
```

Cause:

- The installed `qdrant-client` version no longer exposes `QdrantClient.search()`.
- The current API uses `query_points()`.

Fix made:

- Updated retrieval code to use `query_points(...)`.

Affected file:

- [backend/app/services/retrieval_service.py](/home/yefwang/workspace/llm_chatbot_playground/backend/app/services/retrieval_service.py)

### 4. Local Qdrant storage lock errors

Observed error:

```text
RuntimeError: Storage folder ./qdrant_data is already accessed by another instance of Qdrant client.
If you require concurrent access, use Qdrant server instead.
```

Cause:

- The app was using local file-backed Qdrant via `QdrantClient(path=...)`.
- Local Qdrant only allows one process to access the storage directory at a time.
- Multiple backend-related processes were active at different points:
  - an old uvicorn process
  - a new `run_backend.sh` attempt
  - `seed.py`
  - ad hoc Python probes
- Within a single process, direct re-instantiation also increased the risk of lock/race issues.

Fix made in code:

- Added a process-wide singleton Qdrant client.
- Added a process-wide singleton retrieval service.
- Guarded singleton initialization with a re-entrant lock.

Affected file:

- [backend/app/services/retrieval_service.py](/home/yefwang/workspace/llm_chatbot_playground/backend/app/services/retrieval_service.py)

Important limitation:

- This only solves repeated construction inside one Python process.
- It does not make local Qdrant multi-process safe.
- If two separate Python processes touch `backend/qdrant_data`, the lock error can still happen.

## Wiring changes made

### 5. Retrieval service now reused across the app

Before:

- `RetrievalService()` was being instantiated directly in request handlers and seed code.

After:

- Call sites now use `get_retrieval_service()`.

Affected files:

- [backend/app/api/chat.py](/home/yefwang/workspace/llm_chatbot_playground/backend/app/api/chat.py)
- [backend/app/api/debug.py](/home/yefwang/workspace/llm_chatbot_playground/backend/app/api/debug.py)
- [backend/seed.py](/home/yefwang/workspace/llm_chatbot_playground/backend/seed.py)

## Verification sequence

Once the backend was started cleanly from a single process, the following checks succeeded.

### Health

```bash
curl -sS http://127.0.0.1:8000/health
```

Response:

```json
{"status":"ok"}
```

### Retrieval

```bash
curl -sS 'http://127.0.0.1:8000/debug/retrieve?query=suitcase&top_k=3'
```

Result:

- returned `200 OK`
- returned relevant `suitcases` products

### Chat

```bash
curl -sS --max-time 60 \
  -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"sess_verify_boot","message":"Recommend a lightweight suitcase with spinner wheels"}'
```

Result:

- returned `200 OK`
- generated a recommendation response
- included retrieved product IDs

Example response body:

```json
{
  "session_id": "sess_verify_boot",
  "answer": "The lightest suitcase with spinner wheels is Aster Model 0799 in Gray, weighing 1.11 kg with a 60 L capacity and hard shell. Another option is Aster Model 0419 in Blue, weighing 1.82 kg with a 60 L capacity and soft shell with spinner wheels. Both offer lightweight and spinner wheels.",
  "retrieved_products": [
    "prod_0459",
    "prod_0059",
    "prod_0029",
    "prod_0549",
    "prod_0339",
    "prod_0809",
    "prod_0799",
    "prod_0419"
  ]
}
```

## Useful debugging commands

Health:

```bash
curl -sS http://127.0.0.1:8000/health
```

Chat:

```bash
curl -sS --max-time 60 \
  -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"sess_verify_boot","message":"Recommend a lightweight suitcase with spinner wheels"}'
```

Raw retrieval:

```bash
curl -sS 'http://127.0.0.1:8000/debug/retrieve?query=suitcase&top_k=3'
```

Session transcript:

```bash
curl -sS 'http://127.0.0.1:8000/debug/session/sess_verify_boot'
```

Retrieval events:

```bash
curl -sS 'http://127.0.0.1:8000/debug/retrieval?session_id=sess_verify_boot'
```

Prompt snapshots:

```bash
curl -sS 'http://127.0.0.1:8000/debug/prompts/sess_verify_boot'
```

Combined logs:

```bash
curl -sS 'http://127.0.0.1:8000/debug/logs/sess_verify_boot'
```

Reindex:

```bash
curl -sS -X POST http://127.0.0.1:8000/debug/reindex
```

## Key learnings

1. A valid OpenAI API key does not imply usable quota. Model listing can work while billable inference still fails.
2. ChatGPT Plus billing and OpenAI API billing are separate.
3. Local file-backed Qdrant is single-process. That is the central operational constraint.
4. `uvicorn --reload` can make local-storage debugging more fragile because multiple processes exist over the server lifecycle.
5. For this repo, the safe development pattern is:
   - run only one backend process at a time
   - avoid running `seed.py` while the server is already up
   - avoid extra ad hoc scripts that instantiate Qdrant against the same local path
6. If multi-process access becomes important, the correct long-term fix is to run Qdrant as a separate server rather than embedded local storage.

