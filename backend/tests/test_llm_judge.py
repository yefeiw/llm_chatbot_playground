from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase

from evals.llm_judge import LLMJudge, parse_judge_response


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
            {"score": 0.75, "reason": "Useful ranking.", "criteria": {"ranking_quality": 0.8}}
            ```
            """
        )

        self.assertEqual(parsed["score"], 0.75)
        self.assertEqual(parsed["criteria"]["ranking_quality"], 0.8)

    def test_judge_returns_metric_and_check(self) -> None:
        judge = LLMJudge(
            client=FakeClient(
                '{"score": 0.9, "reason": "Top cards match the request.", '
                '"criteria": {"intent_match": 1, "ranking_quality": 0.8}}'
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
        self.assertEqual(metric.score, 0.9)
        self.assertTrue(check.passed)
