# Evaluation Plan

## Goal

Build an evaluation suite that catches the failure modes we have already seen:

- query rewrite loses or over-carries conversation context
- retrieval returns the wrong category or misses required specs
- answer text and product cards disagree on variants
- answer text and product cards disagree on ranking
- ranking ignores explicit user constraints such as `wireless: yes` and `noise_canceling: yes`
- evidence shown on cards is not actually present in product data
- answer generation duplicates or reorders product lists instead of summarizing the ranked cards

The core product contract is:

1. Retrieval finds candidate products.
2. Variant selection chooses the exact variant shown on each card.
3. Reranking owns card order, evidence, and caveats.
4. Answer generation summarizes the ranked cards and does not create a second product list.

The eval suite should test each boundary separately, then test the end-to-end `/chat` behavior.

For the general search-evaluation concepts behind this plan, see
[`search-evaluation-primer.md`](search-evaluation-primer.md).

## Useful OpenAI Tooling

OpenAI's current docs describe three relevant evaluation paths:

- **Datasets**: a quick way to test prompts in the dashboard before building a full eval.
- **Evals API**: programmatic creation and execution of evals with custom data schemas and graders.
- **Graders**: reusable scoring configs for evals. Supported grader families include string checks, text similarity, score model graders, and Python graders.

Relevant docs:

- Evals guide: https://developers.openai.com/api/docs/guides/evals
- Evals API reference: https://developers.openai.com/api/reference/resources/evals
- Graders guide: https://developers.openai.com/api/docs/guides/graders
- Evaluation best practices: https://developers.openai.com/api/docs/guides/evaluation-best-practices
- Datasets getting started: https://developers.openai.com/api/docs/guides/evaluation-getting-started

The local backend virtualenv currently has `openai==2.30.0`, and `OpenAI().evals` is available. That means we can use the SDK for hosted eval creation/runs when we are ready.

## Recommended Strategy

Use two layers.

### Layer 1: Local Deterministic Evals

Run these in CI or locally without relying on hosted graders. They should be fast, cheap, and strict.

Best for:

- query rewrite invariants
- retrieval category/spec recall
- variant-card consistency
- evidence validity
- answer/card ordering contract
- no product-list leakage in answer text
- response schema compatibility

These are now implemented as a small eval runner under `backend/evals/`.

Run from the repo root:

```bash
PYTHONPATH=backend backend/.venv/bin/python backend/evals/run_eval.py
```

### Layer 2: OpenAI Hosted or Model-Graded Evals

Use OpenAI Evals or score model graders for subjective quality:

- Is the ranking actually helpful for the shopper?
- Are tradeoffs summarized clearly?
- Are caveats useful without being verbose?
- Does the summary align with the card evidence?

Hosted Evals are useful once we have a stable dataset and want to compare prompt/model changes over time.

## Eval Dataset Shape

Start with a JSONL file such as:

```json
{
  "case_id": "headphones_noise_canceling_wireless",
  "messages": [
    {"role": "user", "content": "Recommend noise-canceling wireless headphones"}
  ],
  "expect": {
    "required_category": "headphones",
    "required_specs": {"wireless": "yes", "noise_canceling": "yes"},
    "forbidden_answer_product_list": true,
    "min_matching_cards": 3
  }
}
```

Follow-up cases should include prior turns:

```json
{
  "case_id": "desk_chair_rain_followup",
  "messages": [
    {"role": "user", "content": "Compare comfortable desk chairs under $300"},
    {"role": "assistant", "content": "Previous assistant answer or concise fixture summary."},
    {"role": "user", "content": "I want something I can carry in the rain"}
  ],
  "expect": {
    "query_should_include": ["desk chairs", "rain"],
    "selected_variant_should_match": {
      "prod_0014": {"material": "leatherette", "weight_kg": "1.05"}
    }
  }
}
```

Recommended fields:

- `case_id`
- `messages`
- `expect.required_category`
- `expect.required_specs`
- `expect.forbidden_specs`
- `expect.query_should_include`
- `expect.query_should_not_include`
- `expect.expected_top_product_uids`
- `expect.acceptable_top_product_uids`
- `expect.selected_variant_should_match`
- `expect.min_matching_cards`
- `expect.max_answer_product_names`
- `expect.notes`

## Initial Golden Cases

Seed the eval set with cases based on bugs we already found.

### Query Rewrite

1. `suitcase_followup_cheaper`
   - Turns:
     - "Find a lightweight suitcase with spinner wheels"
     - "show me cheaper ones"
   - Expected rewrite carries: `suitcase`, `lightweight`, `spinner wheels`, `cheaper`.

2. `desk_chair_rain_followup`
   - Turns:
     - "Compare comfortable desk chairs under $300"
     - "I want something I can carry in the rain"
   - Expected rewrite should preserve relevant chair context but should not invent unavailable water-resistance facts.

3. `generic_laptop_recommendation`
   - Prompt: "I want to buy a laptop, any recommendations?"
   - Expected rewrite keeps category broad and does not add unsupported constraints.

### Variant Selection

1. `prod_0014_rain_variant`
   - Product has default Green mesh and secondary Gray leatherette.
   - Rain/carry query should select Gray leatherette if the product is included.

2. `prod_0391_laptop_variant`
   - Product has default 8GB variant and secondary 32GB variant.
   - Generic laptop recommendation can select stronger 32GB variant, but card and context must agree.

### Ranking and Evidence

1. `headphones_noise_canceling_wireless`
   - Required specs: `wireless: yes`, `noise_canceling: yes`.
   - Top-ranked cards should prioritize explicit spec matches over generic category/rating.

2. `laptop_generic_balanced`
   - Ranking can weigh rating, RAM, storage, screen, weight, and price.
   - Evidence must be copied from selected variant specs or product fields.

3. `waterproof_speakers_long_battery`
   - Required specs: `waterproof: yes`, high `battery_hours`.

### Answer Summary

For all cases:

- Answer should not enumerate product names.
- Answer should not introduce product facts absent from card evidence/specs.
- Answer should describe the ranking policy or tradeoffs.
- Product card order is the ranking source of truth.

## Metrics

### Retrieval Metrics

- `category_precision_at_k`: fraction of returned cards in expected category.
- `required_spec_recall_at_k`: whether at least N cards match required specs.
- `candidate_contains_expected_uid`: expected product appears in top-k candidates.

### Query Rewrite Metrics

- `rewrite_contains_required_terms`
- `rewrite_avoids_forbidden_terms`
- `rewrite_preserves_followup_context`
- `rewrite_does_not_invent_constraints`

### Variant Metrics

- `selected_variant_matches_expected_attrs`
- `card_specs_equal_selected_variant_specs`
- `llm_context_specs_equal_card_specs`

### Ranking Metrics

- `top1_in_acceptable_set`
- `top3_contains_required_spec_matches`
- `evidence_is_valid`: every evidence item appears in product fields or selected variant specs.
- `caveats_are_valid`: every caveat appears in allowed caveat options.
- `rank_source_present`: `llm` or `deterministic_fallback`.

For hand-labeled ranking, use:

- `MRR`
- `nDCG@k`
- pairwise ordering accuracy for known comparisons

### Answer Metrics

- `answer_has_no_product_enumeration`
- `answer_has_no_unbacked_product_fact`
- `answer_mentions_cards_or_ranking_policy`
- `answer_does_not_name_non_rank1_as_standout`

## OpenAI Evals API Fit

Hosted Evals are useful for evaluating model outputs once the app can produce structured samples.

Good candidates:

1. **LLM reranker output eval**
   - Sample output: reranker JSON.
   - Deterministic/Python grader checks:
     - product IDs are from candidate set
     - every candidate appears once
     - evidence/caveats are copied from allowed options
   - Score model grader checks:
     - ranking quality relative to request

2. **Answer summary eval**
   - Sample output: final answer.
   - String/Python grader checks:
     - does not contain numbered product list
     - does not contain unexpected product model names
   - Score model grader checks:
     - summary accurately explains tradeoffs and ranked cards

3. **End-to-end chat eval**
   - Sample output: full `/chat` JSON.
   - Python grader checks schema and deterministic invariants.
   - Score model grader checks shopper usefulness.

SDK shape to investigate when implementing:

```python
from openai import OpenAI

client = OpenAI()

eval_obj = client.evals.create(...)
run = client.evals.runs.create(eval_obj.id, ...)
items = client.evals.runs.output_items.list(eval_obj.id, run.id)
```

The exact request bodies should be taken from the OpenAI Evals API reference when implementing, because eval data sources and grader schemas are stricter than normal chat requests.

## Local Eval Harness Proposal

Before using hosted evals, add a local runner:

```text
backend/evals/
  cases/
    retrieval_ranking.jsonl
  run_eval.py
  graders.py
  README.md
```

Runner responsibilities:

1. Load JSONL cases.
2. Create an isolated session ID per case.
3. Send turns through the local FastAPI app or call services directly.
4. Capture:
   - rewritten query
   - raw retrieval hits
   - selected variants
   - ranked results
   - final answer
   - products response
5. Run deterministic graders.
6. Emit JSON and markdown summaries.

Suggested output:

```text
backend/evals/results/YYYYMMDD-HHMM/
  results.json
  summary.md
  failures.json
```

## What Documentation Is Still Missing

Add these when we start implementation:

1. `backend/evals/README.md`
   - how to run local evals
   - how to add cases
   - what metrics mean

2. `backend/evals/cases/README.md`
   - JSONL schema
   - examples
   - labeling guidance

3. `docs/evaluation-plan.md`
   - this plan
   - update as eval harness decisions become code

4. Debug endpoint docs
   - document which fields in `/debug/prompts/{session_id}` and `/debug/retrieval` matter for eval debugging.

5. PR checklist
   - require local eval run summary for retrieval/ranking changes once the harness exists.

## Implementation Order

1. Add local eval case schema and 10-15 golden cases.
2. Add deterministic graders for query rewrite, variant consistency, evidence validity, and answer format.
3. Add local eval runner.
4. Make `/chat` or service layer expose enough intermediate state for evals without scraping logs.
5. Add a small markdown summary report.
6. Add hosted OpenAI Evals for:
   - LLM reranker quality
   - final answer summary quality
7. Add PR checklist and compare eval results before/after retrieval changes.

## Acceptance Criteria for the First Eval Milestone

- At least 10 golden cases covering direct queries, follow-ups, variant selection, and ranking.
- Local eval command runs without network except normal app LLM calls.
- Results include pass/fail per metric and case.
- Failures show enough context to debug:
  - original messages
  - rewritten query
  - selected variants
  - ranked results
  - answer
- The known historical failures are represented as regression cases.
