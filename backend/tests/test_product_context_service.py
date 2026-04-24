from __future__ import annotations

from unittest import TestCase

from app.services.product_context_service import build_retrieval_text


class ProductContextServiceTest(TestCase):
    def test_build_retrieval_text_includes_backend_rank_and_ranking_notes(self) -> None:
        text = build_retrieval_text(
            [
                {
                    "rank": 1,
                    "rerank_reasons": ["high rating 4.8", "32GB RAM"],
                    "payload": {
                        "product_uid": "prod_0391",
                        "title": "Pulse Laptops Model 0391",
                        "brand": "Pulse",
                        "category": "laptops",
                        "price_cents": 174100,
                        "description": "Reliable laptops for everyday use with balanced performance.",
                        "rating": 4.8,
                        "review_count": 2563,
                        "selected_variant": {"variant_name": "Option 2"},
                        "specs": [
                            "color: Gray",
                            "weight_kg: 1.8",
                            "ram_gb: 32",
                            "storage_gb: 256",
                            "screen_inches: 16",
                        ],
                    },
                    "rank_summary": "Best explicit match for the request.",
                    "rank_evidence": ["rating: 4.8", "ram_gb: 32"],
                    "rank_caveats": [],
                }
            ]
        )

        self.assertIn("Rank 1", text)
        self.assertIn("Product prod_0391", text)
        self.assertIn("Selected variant: Option 2", text)
        self.assertIn("Card summary: Best explicit match for the request.", text)
        self.assertIn("Evidence: rating: 4.8, ram_gb: 32", text)
