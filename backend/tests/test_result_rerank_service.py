from __future__ import annotations

from unittest import TestCase

from app.services.result_rerank_service import rerank_hits


class ResultRerankServiceTest(TestCase):
    def test_rerank_moves_stronger_laptop_above_weaker_semantic_match(self) -> None:
        hits = [
            {
                "id": "422",
                "score": 0.589,
                "payload": {
                    "product_uid": "prod_0421",
                    "category": "laptops",
                    "rating": 3.68,
                    "review_count": 2259,
                    "price_cents": 240700,
                    "selected_variant": {
                        "specs": [
                            "color: Black",
                            "weight_kg: 2.7",
                            "ram_gb: 32",
                            "storage_gb: 256",
                            "screen_inches: 14",
                        ]
                    },
                    "specs": [
                        "color: Black",
                        "weight_kg: 2.7",
                        "ram_gb: 32",
                        "storage_gb: 256",
                        "screen_inches: 14",
                    ],
                },
            },
            {
                "id": "392",
                "score": 0.576,
                "payload": {
                    "product_uid": "prod_0391",
                    "category": "laptops",
                    "rating": 4.8,
                    "review_count": 2563,
                    "price_cents": 200000,
                    "selected_variant": {
                        "specs": [
                            "color: Gray",
                            "weight_kg: 1.8",
                            "ram_gb: 32",
                            "storage_gb: 256",
                            "screen_inches: 16",
                        ]
                    },
                    "specs": [
                        "color: Gray",
                        "weight_kg: 1.8",
                        "ram_gb: 32",
                        "storage_gb: 256",
                        "screen_inches: 16",
                    ],
                },
            },
        ]

        ranked = rerank_hits(hits, "laptop recommendations")

        self.assertEqual([hit["payload"]["product_uid"] for hit in ranked], ["prod_0391", "prod_0421"])
        self.assertGreater(ranked[0]["rerank_score"], ranked[1]["rerank_score"])
        self.assertEqual([hit["rank"] for hit in ranked], [1, 2])
        self.assertIn("high rating 4.8", ranked[0]["rerank_reasons"])

    def test_rerank_penalizes_products_over_budget(self) -> None:
        hits = [
            {
                "id": "over",
                "score": 0.9,
                "payload": {
                    "product_uid": "prod_over",
                    "category": "desk_chairs",
                    "rating": 4.8,
                    "review_count": 1000,
                    "price_cents": 50000,
                    "specs": ["material: mesh"],
                },
            },
            {
                "id": "within",
                "score": 0.75,
                "payload": {
                    "product_uid": "prod_within",
                    "category": "desk_chairs",
                    "rating": 4.2,
                    "review_count": 100,
                    "price_cents": 19900,
                    "specs": ["material: mesh"],
                },
            },
        ]

        ranked = rerank_hits(hits, "comfortable desk chairs under $300")

        self.assertEqual(ranked[0]["payload"]["product_uid"], "prod_within")
        self.assertIn("within budget", ranked[0]["rerank_reasons"])
        self.assertIn("over budget", ranked[1]["rerank_reasons"])
