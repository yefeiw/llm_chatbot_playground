from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase

from evals.llm_judge import LLMJudge, normalize_judge_response, parse_judge_response, weighted_judge_score


class FakeResponses:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text

    def create(self, **kwargs):
        return SimpleNamespace(output_text=self.output_text)


class FakeClient:
    def __init__(self, output_text: str) -> None:
        self.responses = FakeResponses(output_text)


class LLMJudgeTest(TestCase):
    def test_parse_judge_response_extracts_json_from_markdown(self) -> None:
        parsed = parse_judge_response(
            """
            ```json
            {"reason": "Useful ranking.", "criteria": {"ranking_quality": {"pass": true, "score": 0.8, "reason": "Good order."}}}
            ```
            """
        )

        self.assertEqual(parsed["criteria"]["ranking_quality"]["score"], 0.8)

    def test_normalize_judge_response_and_weighted_score(self) -> None:
        judged = normalize_judge_response(
            {
                "reason": "Mixed result.",
                "criteria": {
                    "intent_match": {"pass": True, "score": 1, "reason": "Right category."},
                    "hard_constraints": {"pass": False, "score": 0, "reason": "Missed budget."},
                    "ranking_quality": {"pass": True, "score": 1, "reason": "Good top result."},
                    "evidence_grounding": {"pass": True, "score": 1, "reason": "Grounded."},
                    "answer_consistency": {"pass": True, "score": 1, "reason": "No answer."},
                },
            }
        )

        self.assertEqual(judged["criteria"]["hard_constraints"]["score"], 0.0)
        self.assertAlmostEqual(weighted_judge_score(judged), 0.75)

    def test_judge_returns_metric_and_check(self) -> None:
        judge = LLMJudge(
            client=FakeClient(
                """
                {
                  "reason": "Top cards match the request.",
                  "criteria": {
                    "intent_match": {"pass": true, "score": 1, "reason": "Right intent."},
                    "hard_constraints": {"pass": true, "score": 1, "reason": "Wireless is present."},
                    "ranking_quality": {"pass": true, "score": 1, "reason": "Best item first."},
                    "evidence_grounding": {"pass": true, "score": 1, "reason": "Evidence is copied."},
                    "answer_consistency": {"pass": true, "score": 1, "reason": "No answer."}
                  }
                }
                """
            ),
            model="fake-model",
        )

        metric, check = judge.judge(
            {
                "case_id": "headphones",
                "input": {"messages": [{"role": "user", "content": "wireless headphones"}]},
                "expect": {},
            },
            [
                {
                    "rank": 1,
                    "payload": {
                        "product_uid": "prod_a",
                        "title": "A",
                        "category": "headphones",
                        "selected_variant": {"variant_uid": "v1", "variant_name": "Option 1", "specs": ["wireless: yes"]},
                    },
                    "rank_evidence": ["wireless: yes"],
                }
            ],
            retrieval_query="wireless headphones",
            answer=None,
            min_score=0.8,
        )

        self.assertEqual(metric.name, "llm_judge")
        self.assertEqual(metric.score, 1.0)
        self.assertTrue(check.passed)
        self.assertIn("intent_match(weight=0.25", metric.details)
