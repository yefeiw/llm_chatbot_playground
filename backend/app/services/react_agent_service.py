from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from app.core.config import settings
from app.services.embed_service import EmbedService
from app.services.llm_service import LLMService
from app.services.product_context_service import build_retrieval_text
from app.services.query_rewrite_service import QueryRewriteService
from app.services.retrieval_service import RetrievalService


REACT_DEMO_SYSTEM_PROMPT = """You are a demo ReAct-style shopping agent.
Pick one action at a time and return only compact JSON:
{"action": "rewrite_query|retrieve_products|finish", "action_input": "..."}

Available actions:
- rewrite_query: make the latest user request standalone using prior conversation.
- retrieve_products: search the product catalog with a standalone retrieval query.
- finish: answer the user from retrieved product context.

Rules:
- Do not reveal private reasoning.
- Use rewrite_query before retrieve_products for vague follow-ups.
- Use retrieve_products before finish.
- Do not invent products.
"""


@dataclass
class ReActAgentStep:
    step: int
    action: str
    action_input: str | None
    observation: str


@dataclass
class ReActAgentResult:
    answer: str
    hits: list[dict]
    retrieval_query: str
    steps: list[ReActAgentStep] = field(default_factory=list)
    retrieval_latency_ms: float = 0.0
    llm_latency_ms: float = 0.0


class ReActShoppingAgentService:
    """Small demo agent loop around the existing rewrite, retrieval, and answer tools."""

    def __init__(
        self,
        *,
        client: OpenAI | None = None,
        query_rewriter: QueryRewriteService | None = None,
        embedder: EmbedService | None = None,
        retriever: RetrievalService | None = None,
        llm: LLMService | None = None,
        max_steps: int = 5,
    ) -> None:
        self.client = client or OpenAI(api_key=settings.openai_api_key)
        self.query_rewriter = query_rewriter or QueryRewriteService()
        self.embedder = embedder or EmbedService()
        self.retriever = retriever
        self.llm = llm or LLMService()
        self.max_steps = max_steps

    def run(self, user_message: str, prior_memory_text: str, memory_text: str) -> ReActAgentResult:
        steps: list[ReActAgentStep] = []
        retrieval_query = ""
        hits: list[dict] = []
        retrieval_text = ""
        retrieval_latency_ms = 0.0
        answer = ""
        llm_latency_ms = 0.0

        for step_number in range(1, self.max_steps + 1):
            decision = self._choose_action(
                user_message,
                prior_memory_text,
                steps,
                has_retrieval_query=bool(retrieval_query),
                has_hits=bool(hits),
            )
            action = decision["action"]
            action_input = decision.get("action_input")

            if action == "rewrite_query":
                retrieval_query = self.query_rewriter.rewrite(user_message, prior_memory_text)
                steps.append(
                    ReActAgentStep(
                        step=step_number,
                        action=action,
                        action_input=action_input,
                        observation=f"Rewritten retrieval query: {retrieval_query}",
                    )
                )
                continue

            if action == "retrieve_products":
                retrieval_query = (action_input or retrieval_query or user_message).strip()
                t0 = time.perf_counter()
                query_vector = self.embedder.embed_text(retrieval_query)
                if self.retriever is None:
                    raise RuntimeError("Retriever is required for retrieve_products")
                hits = self.retriever.search(query_vector, top_k=settings.retrieval_top_k)
                retrieval_latency_ms += (time.perf_counter() - t0) * 1000
                retrieval_text = build_retrieval_text(hits)
                steps.append(
                    ReActAgentStep(
                        step=step_number,
                        action=action,
                        action_input=retrieval_query,
                        observation=self._summarize_hits(hits),
                    )
                )
                continue

            if action == "finish":
                if not hits:
                    steps.append(
                        ReActAgentStep(
                            step=step_number,
                            action="retrieve_products",
                            action_input=retrieval_query or user_message,
                            observation="Finish requested before retrieval; retrieving products first.",
                        )
                    )
                    continue

                t1 = time.perf_counter()
                answer = self.llm.generate_answer(user_message, memory_text, retrieval_text)
                llm_latency_ms += (time.perf_counter() - t1) * 1000
                steps.append(
                    ReActAgentStep(
                        step=step_number,
                        action=action,
                        action_input=None,
                        observation="Final answer generated from retrieved product context.",
                    )
                )
                break

        if not retrieval_query:
            retrieval_query = user_message.strip()

        if not hits:
            t0 = time.perf_counter()
            query_vector = self.embedder.embed_text(retrieval_query)
            if self.retriever is None:
                raise RuntimeError("Retriever is required for retrieve_products")
            hits = self.retriever.search(query_vector, top_k=settings.retrieval_top_k)
            retrieval_latency_ms += (time.perf_counter() - t0) * 1000
            retrieval_text = build_retrieval_text(hits)
            steps.append(
                ReActAgentStep(
                    step=len(steps) + 1,
                    action="retrieve_products",
                    action_input=retrieval_query,
                    observation=self._summarize_hits(hits),
                )
            )

        if not answer:
            t1 = time.perf_counter()
            answer = self.llm.generate_answer(user_message, memory_text, retrieval_text)
            llm_latency_ms += (time.perf_counter() - t1) * 1000
            steps.append(
                ReActAgentStep(
                    step=len(steps) + 1,
                    action="finish",
                    action_input=None,
                    observation="Final answer generated from retrieved product context.",
                )
            )

        return ReActAgentResult(
            answer=answer,
            hits=hits,
            retrieval_query=retrieval_query,
            steps=steps,
            retrieval_latency_ms=retrieval_latency_ms,
            llm_latency_ms=llm_latency_ms,
        )

    def _choose_action(
        self,
        user_message: str,
        prior_memory_text: str,
        steps: list[ReActAgentStep],
        has_retrieval_query: bool,
        has_hits: bool,
    ) -> dict[str, str | None]:
        response = self.client.responses.create(
            model=settings.openai_chat_model,
            input=[
                {"role": "system", "content": REACT_DEMO_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Prior conversation:\n{prior_memory_text or '(none)'}\n\n"
                        f"Latest user request:\n{user_message.strip()}\n\n"
                        f"Completed actions:\n{self._format_steps(steps)}\n\n"
                        "Choose the next action."
                    ),
                },
            ],
            max_output_tokens=120,
        )
        decision = self._parse_action(response.output_text)
        if decision["action"] in {"rewrite_query", "retrieve_products", "finish"}:
            return decision

        if not has_retrieval_query:
            return {"action": "rewrite_query", "action_input": user_message.strip()}
        if not has_hits:
            return {"action": "retrieve_products", "action_input": None}
        return {"action": "finish", "action_input": None}

    @staticmethod
    def _parse_action(text: str) -> dict[str, str | None]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = [line for line in cleaned.splitlines() if not line.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        try:
            payload: Any = json.loads(cleaned)
        except json.JSONDecodeError:
            return {"action": "invalid", "action_input": None}

        action = str(payload.get("action") or "").strip()
        action_input = payload.get("action_input")
        if action_input is not None:
            action_input = str(action_input).strip() or None
        return {"action": action, "action_input": action_input}

    @staticmethod
    def _format_steps(steps: list[ReActAgentStep]) -> str:
        if not steps:
            return "(none)"
        return "\n".join(
            f"{step.step}. action={step.action}; input={step.action_input or ''}; observation={step.observation}"
            for step in steps
        )

    @staticmethod
    def _summarize_hits(hits: list[dict]) -> str:
        if not hits:
            return "Retrieved 0 products."

        product_summaries = []
        for hit in hits[:3]:
            payload = hit.get("payload") or {}
            product_summaries.append(
                f"{payload.get('product_uid')}: {payload.get('title')} (score={hit.get('score')})"
            )
        return f"Retrieved {len(hits)} products. Top matches: " + "; ".join(product_summaries)
