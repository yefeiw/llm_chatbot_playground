from __future__ import annotations

from unittest import TestCase

from evals.graders import grade_case_output


class EvalGradersTest(TestCase):
    def test_grade_case_output_passes_variant_and_evidence_contracts(self) -> None:
        case = {
            "case_id": "variant_contract",
            "expect": {
                "required_category": "headphones",
                "required_specs": {"wireless": "yes", "noise_canceling": "yes"},
                "selected_variant_should_match": {
                    "prod_a": {"wireless": "yes", "noise_canceling": "yes"}
                },
                "card_specs_equal_selected_variant_specs": True,
                "rank_source_present": True,
                "evidence_is_valid": True,
            },
        }
        hits = [
            {
                "rank": 1,
                "rank_source": "deterministic_fallback",
                "rank_evidence": ["category: headphones", "wireless: yes", "noise_canceling: yes"],
                "payload": {
                    "product_uid": "prod_a",
                    "title": "A",
                    "brand": "Aster",
                    "category": "headphones",
                    "price_cents": 12000,
                    "rating": 4.5,
                    "review_count": 100,
                    "selected_variant": {
                        "variant_name": "Option 1",
                        "specs": ["wireless: yes", "noise_canceling: yes"],
                    },
                    "specs": ["wireless: yes", "noise_canceling: yes"],
                },
            }
        ]

        result = grade_case_output(case, hits, retrieval_query="wireless noise-canceling headphones")

        self.assertTrue(result.passed)
        self.assertEqual(result.passed_count, len(result.checks))

    def test_grade_case_output_fails_invalid_evidence(self) -> None:
        case = {
            "case_id": "bad_evidence",
            "expect": {"evidence_is_valid": True},
        }
        hits = [
            {
                "rank_evidence": ["invented: yes"],
                "payload": {
                    "product_uid": "prod_a",
                    "title": "A",
                    "brand": "Aster",
                    "category": "headphones",
                    "price_cents": 12000,
                    "rating": 4.5,
                    "review_count": 100,
                    "selected_variant": {
                        "variant_name": "Option 1",
                        "specs": ["wireless: yes"],
                    },
                    "specs": ["wireless: yes"],
                },
            }
        ]

        result = grade_case_output(case, hits, retrieval_query="headphones")

        self.assertFalse(result.passed)
        self.assertEqual(result.checks[0].name, "evidence_is_valid")
