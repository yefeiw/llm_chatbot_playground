from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase

from app.services.react_agent_service import ReActShoppingAgentService


class FakeResponses:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.outputs:
            return SimpleNamespace(output_text=self.outputs.pop(0))
        return SimpleNamespace(output_text='{"action": "finish", "action_input": null}')


class FakePlannerClient:
    def __init__(self, outputs: list[str]) -> None:
        self.responses = FakeResponses(outputs)


class FakeQueryRewriter:
    def rewrite(self, user_message: str, memory_text: str) -> str:
        return "cheaper lightweight suitcases with spinner wheels"


class FakeEmbedder:
    def __init__(self) -> None:
        self.text: str | None = None

    def embed_text(self, text: str) -> list[float]:
        self.text = text
        return [0.1, 0.2, 0.3]


class FakeRetriever:
    def __init__(self) -> None:
        self.vector: list[float] | None = None

    def search(self, vector: list[float], top_k: int) -> list[dict]:
        self.vector = vector
        return [
            {
                "id": "prod_1",
                "score": 0.91,
                "payload": {
                    "product_uid": "prod_1",
                    "title": "Aster Suitcase",
                    "brand": "Aster",
                    "category": "suitcases",
                    "description": "Lightweight suitcase with spinner wheels.",
                    "rating": 4.7,
                    "review_count": 2301,
                    "specs": ["weight_kg: 2.1", "spinner_wheels: yes"],
                },
            }
        ]


class FakeLLM:
    def __init__(self) -> None:
        self.user_message: str | None = None
        self.retrieval_text: str | None = None

    def generate_answer(self, user_message: str, memory_text: str, retrieval_text: str) -> str:
        self.user_message = user_message
        self.retrieval_text = retrieval_text
        return "The Aster Suitcase is a cheaper lightweight option."


class ReActShoppingAgentServiceTest(TestCase):
    def test_run_executes_rewrite_retrieve_and_finish_actions(self) -> None:
        planner = FakePlannerClient(
            [
                '{"action": "rewrite_query", "action_input": "show me cheaper ones"}',
                '{"action": "retrieve_products", "action_input": null}',
                '{"action": "finish", "action_input": null}',
            ]
        )
        embedder = FakeEmbedder()
        retriever = FakeRetriever()
        llm = FakeLLM()
        service = ReActShoppingAgentService(
            client=planner,
            query_rewriter=FakeQueryRewriter(),
            embedder=embedder,
            retriever=retriever,
            llm=llm,
        )

        result = service.run(
            "show me cheaper ones",
            "user: I need a lightweight suitcase with spinner wheels",
            "user: I need a lightweight suitcase with spinner wheels\nuser: show me cheaper ones",
        )

        self.assertEqual(result.retrieval_query, "cheaper lightweight suitcases with spinner wheels")
        self.assertEqual(embedder.text, "cheaper lightweight suitcases with spinner wheels")
        self.assertEqual(retriever.vector, [0.1, 0.2, 0.3])
        self.assertEqual(llm.user_message, "show me cheaper ones")
        self.assertIn("Aster Suitcase", llm.retrieval_text or "")
        self.assertEqual([step.action for step in result.steps], ["rewrite_query", "retrieve_products", "finish"])
        self.assertEqual(result.answer, "The Aster Suitcase is a cheaper lightweight option.")

    def test_invalid_planner_output_falls_back_to_required_actions(self) -> None:
        planner = FakePlannerClient(["not json", "not json", "not json"])
        service = ReActShoppingAgentService(
            client=planner,
            query_rewriter=FakeQueryRewriter(),
            embedder=FakeEmbedder(),
            retriever=FakeRetriever(),
            llm=FakeLLM(),
        )

        result = service.run("show me cheaper ones", "", "user: show me cheaper ones")

        self.assertEqual(result.retrieval_query, "cheaper lightweight suitcases with spinner wheels")
        self.assertEqual([step.action for step in result.steps], ["rewrite_query", "retrieve_products", "finish"])
