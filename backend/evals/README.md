# Local Evaluation Harness

This directory contains deterministic evals for the shopping assistant's retrieval, variant, ranking, evidence, and answer-shape contracts.

The default runner does not call OpenAI. It uses the deterministic mock catalog, an in-memory SQLite variant table, query fixtures, variant selection, and the deterministic fallback reranker. Use this layer for fast local checks and CI.

Run from the repo root:

```bash
PYTHONPATH=backend backend/.venv/bin/python backend/evals/run_eval.py
```

Machine-readable output:

```bash
PYTHONPATH=backend backend/.venv/bin/python backend/evals/run_eval.py --json
```

Optional live checks:

```bash
PYTHONPATH=backend backend/.venv/bin/python backend/evals/run_eval.py --live-query-rewrite
PYTHONPATH=backend backend/.venv/bin/python backend/evals/run_eval.py --live-llm-rerank
```

The live flags call OpenAI-backed services and are intentionally opt-in. They are useful for prompt/model comparisons, but the deterministic default is the gate for product-card consistency and ranking contract regressions.

## What This Catches

- rewritten retrieval queries missing required carried context
- wrong product category in ranked cards
- selected variant not matching the query
- card specs disagreeing with selected variant specs
- ranking missing a source
- evidence that is not copied from allowed product/card fields
- answers that reintroduce numbered product lists

## Files

- `cases/retrieval_ranking.jsonl`: initial golden cases based on bugs already observed.
- `graders.py`: deterministic graders for local invariants.
- `run_eval.py`: CLI runner.

## OpenAI Evals

OpenAI hosted evals should be added after this JSONL schema has settled. Good hosted eval candidates are subjective ranking quality and answer-summary usefulness; keep exact product-card invariants in the local graders.
