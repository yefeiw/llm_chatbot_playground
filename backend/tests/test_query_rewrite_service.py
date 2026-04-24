from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase

from app.services.query_rewrite_service import QueryRewriteService


class FakeResponses:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=self.output_text)


class FakeClient:
    def __init__(self, output_text: str) -> None:
        self.responses = FakeResponses(output_text)


class QueryRewriteServiceTest(TestCase):
    def test_rewrite_uses_history_and_latest_message(self) -> None:
        client = FakeClient(' "cheaper lightweight suitcases with spinner wheels" ')
        service = QueryRewriteService(client=client)

        rewritten = service.rewrite(
            "show me cheaper ones",
            "user: I need a lightweight suitcase with spinner wheels\nassistant: Here are some options.",
        )

        self.assertEqual(rewritten, "cheaper lightweight suitcases with spinner wheels")
        call = client.responses.calls[0]
        self.assertEqual(call["model"], "gpt-4.1-mini")
        self.assertEqual(call["max_output_tokens"], 120)
        self.assertIn("show me cheaper ones", call["input"][1]["content"])
        self.assertIn("lightweight suitcase with spinner wheels", call["input"][1]["content"])

    def test_empty_message_returns_empty_without_calling_openai(self) -> None:
        client = FakeClient("unused")
        service = QueryRewriteService(client=client)

        rewritten = service.rewrite("   ", "user: backpacks")

        self.assertEqual(rewritten, "")
        self.assertEqual(client.responses.calls, [])

    def test_blank_rewrite_falls_back_to_original_query(self) -> None:
        service = QueryRewriteService(client=FakeClient("   "))

        rewritten = service.rewrite("Recommend headphones", "")

        self.assertEqual(rewritten, "Recommend headphones")
