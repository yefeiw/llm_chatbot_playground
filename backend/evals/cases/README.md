# Eval Cases

Cases are JSONL: one JSON object per line.

Minimal shape:

```json
{
  "case_id": "headphones_noise_canceling_wireless",
  "input": {
    "messages": [{"role": "user", "content": "Recommend noise-canceling wireless headphones"}],
    "retrieval_query": "noise-canceling wireless headphones recommendations",
    "candidate_product_uids": ["prod_0225", "prod_0660"]
  },
  "expect": {
    "required_category": "headphones",
    "required_specs": {"wireless": "yes", "noise_canceling": "yes"},
    "graded_relevance": {"prod_0225": 3, "prod_0660": 3},
    "precision_at_k": {"k": 2, "min": 1.0, "relevant_threshold": 2},
    "recall_at_k": {"k": 2, "min": 1.0, "relevant_threshold": 2},
    "mrr": {"k": 2, "min": 1.0, "relevant_threshold": 2},
    "ndcg_at_k": {"k": 2, "min": 0.9},
    "wpr_at_k": {"k": 2, "min": 0.9, "position_weights": [1.0, 0.8]},
    "min_matching_cards": 2,
    "card_specs_equal_selected_variant_specs": true,
    "rank_source_present": true,
    "evidence_is_valid": true
  }
}
```

Supported expectations:

- `query_should_include`
- `query_should_not_include`
- `required_category`
- `required_specs`
- `min_matching_cards`
- `graded_relevance`
- `precision_at_k`
- `recall_at_k`
- `mrr`
- `ndcg_at_k`
- `wpr_at_k`
- `selected_variant_should_match`
- `card_specs_equal_selected_variant_specs`
- `acceptable_top_product_uids`
- `expected_top_product_uids`
- `rank_source_present`
- `evidence_is_valid`
- `forbidden_answer_product_list`
- `max_answer_product_names`
