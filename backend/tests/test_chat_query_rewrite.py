from __future__ import annotations

import json
from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api import chat as chat_module
from app.db.models import Base, LLMEvent, Message, RetrievalEvent, Session
from app.schemas.chat import ChatRequest


class FakeEmbedder:
    def __init__(self) -> None:
        self.text: str | None = None

    def embed_text(self, text: str) -> list[float]:
        self.text = text
        return [0.1, 0.2, 0.3]


class FakeRetriever:
    def __init__(self) -> None:
        self.vector: list[float] | None = None
        self.top_k: int | None = None

    def search(self, vector: list[float], top_k: int) -> list[dict]:
        self.vector = vector
        self.top_k = top_k
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
                    "price_cents": 9900,
                    "image_url": "/product-images/categories/suitcases.svg",
                    "product_url": "/products/prod_1",
                    "rating": 4.7,
                    "review_count": 2301,
                    "selected_variant": {
                        "variant_uid": "var_prod_1_0",
                        "variant_name": "Option 1",
                        "is_default": True,
                        "specs": ["weight_kg: 2.1", "spinner_wheels: yes"],
                    },
                    "specs": ["weight_kg: 2.1", "spinner_wheels: yes"],
                },
            }
        ]


class FakeQueryRewriter:
    def __init__(self, rewritten_query: str) -> None:
        self.rewritten_query = rewritten_query
        self.user_message: str | None = None
        self.memory_text: str | None = None

    def rewrite(self, user_message: str, memory_text: str) -> str:
        self.user_message = user_message
        self.memory_text = memory_text
        return self.rewritten_query


class FakeLLM:
    def __init__(self) -> None:
        self.user_message: str | None = None
        self.memory_text: str | None = None
        self.retrieval_text: str | None = None

    def generate_answer(self, user_message: str, memory_text: str, retrieval_text: str) -> str:
        self.user_message = user_message
        self.memory_text = memory_text
        self.retrieval_text = retrieval_text
        return "The Aster Suitcase is the cheaper matching option."


class FakeReranker:
    def rerank(self, hits: list[dict], user_message: str, retrieval_query: str) -> list[dict]:
        for index, hit in enumerate(hits, start=1):
            hit["rank"] = index
            hit["rank_source"] = "test"
            hit["rank_evidence"] = ["weight_kg: 2.1"]
            hit["rank_caveats"] = []
            hit["rank_summary"] = "Matches the rewritten query."
        return hits


class ChatQueryRewriteTest(TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = sessionmaker(bind=engine, autocommit=False, autoflush=False)()

        self.db.add(Session(session_uid="sess_rewrite"))
        self.db.add(
            Message(
                session_uid="sess_rewrite",
                role="user",
                content="I need a lightweight suitcase with spinner wheels",
            )
        )
        self.db.add(
            Message(
                session_uid="sess_rewrite",
                role="assistant",
                content="Here are some suitcase options.",
            )
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_chat_embeds_and_logs_rewritten_query(self) -> None:
        embedder = FakeEmbedder()
        retriever = FakeRetriever()
        rewriter = FakeQueryRewriter("cheaper lightweight suitcases with spinner wheels")
        llm = FakeLLM()

        with (
            patch.object(chat_module, "EmbedService", return_value=embedder),
            patch.object(chat_module, "get_retrieval_service", return_value=retriever),
            patch.object(chat_module, "QueryRewriteService", return_value=rewriter),
            patch.object(chat_module, "LLMRerankService", return_value=FakeReranker()),
            patch.object(chat_module, "LLMService", return_value=llm),
        ):
            response = chat_module.chat(
                ChatRequest(session_id="sess_rewrite", message="show me cheaper ones"),
                db=self.db,
            )

        self.assertEqual(response.answer, "The Aster Suitcase is the cheaper matching option.")
        self.assertEqual(response.products[0].product_uid, "prod_1")
        self.assertEqual(response.products[0].rank, 1)
        self.assertEqual(embedder.text, "cheaper lightweight suitcases with spinner wheels")
        self.assertEqual(retriever.vector, [0.1, 0.2, 0.3])
        self.assertEqual(rewriter.user_message, "show me cheaper ones")
        self.assertIn("lightweight suitcase with spinner wheels", rewriter.memory_text or "")
        self.assertNotIn("show me cheaper ones", rewriter.memory_text or "")
        self.assertEqual(llm.user_message, "show me cheaper ones")

        retrieval_event = self.db.scalar(select(RetrievalEvent))
        self.assertIsNotNone(retrieval_event)
        self.assertEqual(retrieval_event.query_text, "cheaper lightweight suitcases with spinner wheels")

        llm_event = self.db.scalar(select(LLMEvent))
        self.assertIsNotNone(llm_event)
        snapshot = json.loads(llm_event.prompt_snapshot_json)
        self.assertEqual(snapshot["user_message"], "show me cheaper ones")
        self.assertEqual(snapshot["retrieval_query"], "cheaper lightweight suitcases with spinner wheels")
        self.assertTrue(snapshot["query_rewritten"])
        ranked_result = snapshot["ranked_results"][0]
        self.assertEqual(ranked_result["rank"], 1)
        self.assertEqual(ranked_result["product_uid"], "prod_1")
        self.assertEqual(ranked_result["title"], "Aster Suitcase")
        self.assertEqual(ranked_result["variant_uid"], "var_prod_1_0")
        self.assertEqual(ranked_result["variant_name"], "Option 1")
        self.assertIn("rerank_score", ranked_result)
        self.assertIn("rerank_reasons", ranked_result)
        self.assertEqual(ranked_result["rank_source"], "test")
        self.assertEqual(ranked_result["evidence"], ["weight_kg: 2.1"])
        self.assertEqual(snapshot["answer"], "The Aster Suitcase is the cheaper matching option.")
