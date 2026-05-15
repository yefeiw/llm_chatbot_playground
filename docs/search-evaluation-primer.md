# Search Evaluation Primer

This note describes how to evaluate a search system in general, independent of the current shopping-assistant implementation.

## Core Idea

A search evaluation needs three ingredients:

1. **Corpus**: the set of searchable items.
2. **Information needs**: what users are trying to accomplish.
3. **Relevance judgments**: labels saying which items satisfy each information need.

The important distinction is that relevance is judged against the user's information need, not just the literal query text. A query like `python` is ambiguous; the information need disambiguates whether the user means the programming language, a pet, a book, or something else.

In TREC terminology:

- A user need is a **topic**.
- The judged query-item labels are **qrels**.
- One system's ranked output is a **run**.
- A reusable corpus plus topics plus judgments is a **test collection**.

## Offline vs Online Evaluation

Use both.

### Offline Evaluation

Offline evals run against a fixed dataset and labels. They are best for:

- catching regressions before shipping
- comparing retrieval algorithms
- tuning ranking features
- measuring search quality by query segment
- debugging exact failure cases

This is what `backend/evals` currently starts to provide.

### Online Evaluation

Online evals measure real user behavior. They are best for:

- A/B testing production ranking changes
- measuring click-through, add-to-cart, conversion, reformulation, dwell time, abandonment, or successful task completion
- detecting cases where offline labels do not match real user behavior

Online metrics are useful but noisy. A product can get clicks for reasons unrelated to relevance, such as image quality, brand popularity, price, or position bias.

## Build a Good Test Collection

Start with a representative set of information needs. For a product search system, include:

- head queries: `headphones`, `laptop`, `chair`
- specific intent: `wireless noise canceling headphones`
- constraints: `desk chair under $300`, `waterproof speaker long battery`
- follow-ups: `show me cheaper ones`, `something I can carry in the rain`
- ambiguous queries: `apple`, `charger`, `light`
- negative or impossible cases: `waterproof laptop under $50`
- typo and synonym cases: `noice cancelling`, `carry-on luggage`
- long natural-language queries
- category boundary cases: `gaming headset` vs `headphones`

Each case should store:

- `case_id`
- information need
- raw user query or conversation turns
- candidate corpus version
- required/forbidden attributes
- relevance judgments
- notes about ambiguity

Do not tune on the final test set. Keep at least:

- a **dev set** for prompt/ranker/filter tuning
- a **test set** for unbiased reporting
- a **regression set** for known bugs that must never come back

## Judgment Types

### Binary Judgments

Binary labels are simple:

- `1`: relevant
- `0`: not relevant

Use binary judgments for early evals and hard filters like wrong category or missing required specs.

### Graded Judgments

Graded labels capture degrees of usefulness:

- `3`: excellent match
- `2`: good match
- `1`: weak/partial match
- `0`: not relevant

Use graded judgments when ranking quality matters. For example, a wireless noise-canceling headphone is a better match than a wireless headphone without noise canceling, even if both are headphones.

### Attribute-Based Judgments

For structured product search, many judgments can be derived from catalog attributes:

- category match
- price within budget
- required spec present
- forbidden spec absent
- selected variant matches the visible card
- stock/inventory eligibility

These are cheaper and more consistent than manual labels. They do not replace human judgments, because users also care about tradeoffs like brand, reviews, design, and overall value.

## Search Metrics

Pick metrics based on the user experience.

### Precision@k

`precision@k` asks: of the top `k` results, how many are relevant?

Use it when users mostly inspect the first page or first few cards.

Good for:

- product search top cards
- autocomplete suggestions
- search result pages

### Recall@k

`recall@k` asks: of all relevant items, how many did we retrieve in the top `k`?

Use it when missing relevant items is expensive.

Good for:

- legal/e-discovery search
- support knowledge bases
- medical/scientific search
- candidate generation before reranking

### MRR

Mean Reciprocal Rank focuses on the rank of the first relevant result.

Use it when one good answer is enough.

Good for:

- known-item search
- help-center search
- navigational queries

### MAP

Mean Average Precision rewards systems that rank all relevant items early.

Use it when there can be many relevant items and binary labels are acceptable.

Good for:

- document retrieval
- broad product/category search

### nDCG@k

Normalized Discounted Cumulative Gain supports graded relevance and discounts lower ranks.

Use it when top-ranked order and relevance degree both matter.

Good for:

- ecommerce search
- recommendations
- semantic search
- hybrid lexical/vector ranking

For this shopping assistant, `nDCG@k`, `precision@k`, and targeted constraint checks are the most useful offline metrics.

### WPR@k

`WPR` is not a single standard acronym across information retrieval literature. If we use it in this project, we should define it before reporting it.

Recommended project definition:

```text
WPR@k = weighted precision at k
      = sum(position_weight_i * normalized_relevance_i) / sum(position_weight_i)
```

This is useful when product slots have different business or UX importance. For example, card 1 may matter more than card 5, and card 5 may matter more than card 8. Unlike `nDCG`, which uses a standard logarithmic discount, `WPR@k` lets us choose explicit weights such as `[1.0, 0.8, 0.6, 0.4, 0.2]`.

Use `WPR@k` for a practical top-of-list score that stakeholders can understand. Use `nDCG@k` as the more standard IR metric for graded ranking quality.

## Debug Metrics

Aggregate metrics are not enough. Track diagnostic metrics by stage:

### Query Understanding

- rewrite preserves user intent
- rewrite carries relevant prior context
- rewrite does not invent constraints
- extracted filters match the query
- category classifier accuracy

### Candidate Retrieval

- candidate set contains at least one good result
- category precision@k
- required spec recall@k
- expected product appears in top-k
- lexical vs vector recall

### Filtering

- no required matches are filtered out
- invalid products are removed
- price/availability filters are correct
- filters are explainable

### Reranking

- top1 in acceptable set
- nDCG@k
- WPR@k if the product/UI team has custom position weights
- pairwise preference accuracy
- required specs outrank partial matches
- ranking is stable under small prompt/query changes

### Presentation

- displayed card matches ranked item
- displayed variant matches evidence
- evidence is copied from indexed/catalog fields
- generated answer does not contradict results

## Human Labeling Guidelines

A label guide should define:

- the user need
- what counts as relevant
- what counts as partially relevant
- required constraints
- disqualifying constraints
- examples of edge cases

For products, judges should consider:

- category correctness
- required specs
- price constraints
- variant-specific attributes
- stock/availability if present
- whether the item would reasonably satisfy the shopper

Use multiple judges for subjective cases and track agreement. When judges disagree, clarify the guideline or mark the case ambiguous.

## Common Pitfalls

- **Evaluating only happy paths**: include typos, ambiguity, follow-ups, and impossible requests.
- **Judging query text instead of intent**: labels should target the information need.
- **Tuning on the test set**: keep dev and test separate.
- **Using accuracy**: search is highly imbalanced; most corpus items are irrelevant.
- **Only measuring average score**: slice by category, query type, constraint type, and head/tail queries.
- **Ignoring position bias online**: clicks are affected by rank and UI.
- **Ignoring catalog freshness**: labels can go stale when product data changes.
- **Letting generated answers hide search failures**: evaluate retrieval/ranking separately from answer generation.

## Recommended Path for This Project

1. Keep the current local deterministic evals as the regression gate.
2. Expand cases from 6 to roughly 50 information needs across categories.
3. Add graded relevance labels for top candidate products.
4. Implement `precision@k`, `recall@k`, `MRR`, `nDCG@k`, and project-defined `WPR@k`.
5. Add slices:
   - category
   - query type
   - follow-up vs first-turn
   - strict constraints vs broad recommendations
   - variant-sensitive vs product-level
6. Add a small manual review workflow for new bug reports.
7. Use hosted/model-graded evals later for subjective summary quality, not for hard product-card invariants.

## References

- Stanford IR book, evaluation overview: https://nlp.stanford.edu/IR-book/html/htmledition/information-retrieval-system-evaluation-1.html
- Stanford IR book, precision and recall: https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-unranked-retrieval-sets-1.html
- NIST TREC "How To TREC": https://trec.nist.gov/howto.html
- Järvelin and Kekäläinen, 2002, cumulated gain-based evaluation: https://doi.org/10.1145/582415.582418
