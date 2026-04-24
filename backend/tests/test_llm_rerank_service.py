from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase

from app.services.llm_rerank_service import LLMRerankService


class FakeResponses:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text

    def create(self, **kwargs):
        return SimpleNamespace(output_text=self.output_text)


class FakeClient:
    def __init__(self, output_text: str) -> None:
        self.responses = FakeResponses(output_text)


class LLMRerankServiceTest(TestCase):
    def test_rerank_applies_valid_llm_rank_and_filters_evidence(self) -> None:
        client = FakeClient(
            """
            {
              "ranked_results": [
                {
                  "product_uid": "prod_b",
                  "evidence": ["noise_canceling: yes", "wireless: yes", "invented: no"],
                  "caveats": [],
                  "summary": "Best explicit match for the requested features."
                },
                {
                  "product_uid": "prod_a",
                  "evidence": ["rating: 4.8"],
                  "caveats": ["noise_canceling: no"],
                  "summary": "Higher rating but misses noise canceling."
                }
              ]
            }
            """
        )
        service = LLMRerankService(client=client)
        hits = [
            {
                "score": 0.8,
                "payload": {
                    "product_uid": "prod_a",
                    "title": "A",
                    "brand": "Aster",
                    "category": "headphones",
                    "price_cents": 12000,
                    "rating": 4.8,
                    "review_count": 100,
                    "selected_variant": {"variant_name": "Option 1", "specs": ["wireless: yes", "noise_canceling: no"]},
                    "specs": ["wireless: yes", "noise_canceling: no"],
                },
            },
            {
                "score": 0.7,
                "payload": {
                    "product_uid": "prod_b",
                    "title": "B",
                    "brand": "Nova",
                    "category": "headphones",
                    "price_cents": 14000,
                    "rating": 4.0,
                    "review_count": 50,
                    "selected_variant": {"variant_name": "Option 1", "specs": ["wireless: yes", "noise_canceling: yes"]},
                    "specs": ["wireless: yes", "noise_canceling: yes"],
                },
            },
        ]

        ranked = service.rerank(hits, "noise-canceling wireless headphones", "noise-canceling wireless headphones")

        self.assertEqual([hit["payload"]["product_uid"] for hit in ranked], ["prod_b", "prod_a"])
        self.assertEqual([hit["rank"] for hit in ranked], [1, 2])
        self.assertEqual(ranked[0]["rank_source"], "llm")
        self.assertEqual(ranked[0]["rank_evidence"], ["noise_canceling: yes", "wireless: yes"])
        self.assertEqual(ranked[1]["rank_caveats"], ["noise_canceling: no"])

    def test_invalid_llm_response_falls_back_to_deterministic_ranker(self) -> None:
        service = LLMRerankService(client=FakeClient("not json"))

        ranked = service.rerank(
            [
                {
                    "score": 0.8,
                    "payload": {
                        "product_uid": "prod_a",
                        "category": "headphones",
                        "rating": 4.8,
                        "review_count": 100,
                        "price_cents": 12000,
                        "specs": ["wireless: yes"],
                    },
                }
            ],
            "headphones",
            "headphones",
        )

        self.assertEqual(ranked[0]["rank_source"], "deterministic_fallback")
        self.assertEqual(ranked[0]["rank"], 1)
