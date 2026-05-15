from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from app.core.config import settings
from evals.graders import EvalCheck, EvalMetric


LLM_JUDGE_SYSTEM_PROMPT = """You are an expert search-quality judge for a shopping search system.
Return only compact JSON:
{"score":0.0,"reason":"...","criteria":{"intent_match":0.0,"ranking_quality":0.0,"evidence_quality":0.0,"answer_quality":0.0}}

Scoring rules:
- Use a 0.0 to 1.0 score.
- Judge whether the ranked product cards satisfy the user's information need.
- Reward exact category/spec matches, strong top-of-list ordering, useful tradeoffs, and evidence grounded in product fields.
- Penalize missing required constraints, irrelevant categories, weak top results, invented facts, and answer text that contradicts cards.
- If no answer is provided, set answer_quality to 1.0 unless the ranking itself needs an answer to be judged.
- Do not require every product to be perfect; focus on top-ranked usefulness and whether visible evidence supports the recommendation.
- Keep reason to one sentence.
"""


class LLMJudge:
    def __init__(self, client: OpenAI | None = None, model: str | None = None) -> None:
        self.client = client or OpenAI(api_key=settings.openai_api_key)
        self.model = model or settings.openai_chat_model

    def judge(
        self,
        case: dict[str, Any],
        hits: list[dict[str, Any]],
        *,
        retrieval_query: str,
        answer: str | None,
        min_score: float,
    ) -> tuple[EvalMetric, EvalCheck]:
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": LLM_JUDGE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "case_id": case.get("case_id"),
                            "messages": (case.get("input") or {}).get("messages", []),
                            "retrieval_query": retrieval_query,
                            "expectations": case.get("expect", {}),
                            "ranked_products": [_product_for_judge(hit) for hit in hits],
                            "answer": answer,
                        }
                    ),
                },
            ],
            max_output_tokens=800,
        )
        judged = parse_judge_response(response.output_text)
        score = _clamp_score(judged.get("score"))
        reason = _clean_reason(judged.get("reason"))
        criteria = judged.get("criteria") if isinstance(judged.get("criteria"), dict) else {}
        criteria_text = ", ".join(
            f"{name}={_clamp_score(value):.2f}"
            for name, value in criteria.items()
        )
        details = f"score={score:.4f}; minimum={min_score:.4f}; reason={reason}"
        if criteria_text:
            details = f"{details}; criteria={criteria_text}"

        metric = EvalMetric(name="llm_judge", score=score, details=details)
        check = EvalCheck(name="llm_judge", passed=score >= min_score, details=details)
        return metric, check


def parse_judge_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = [line for line in cleaned.splitlines() if not line.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    if not cleaned.startswith("{"):
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in LLM judge response")
        cleaned = match.group(0)

    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("LLM judge response must be a JSON object")
    return payload


def _product_for_judge(hit: dict[str, Any]) -> dict[str, Any]:
    payload = hit.get("payload") or {}
    selected_variant = payload.get("selected_variant")
    return {
        "rank": hit.get("rank"),
        "product_uid": payload.get("product_uid"),
        "title": payload.get("title"),
        "category": payload.get("category"),
        "price_cents": payload.get("price_cents"),
        "rating": payload.get("rating"),
        "review_count": payload.get("review_count"),
        "selected_variant": {
            "variant_uid": selected_variant.get("variant_uid"),
            "variant_name": selected_variant.get("variant_name"),
            "specs": selected_variant.get("specs", []),
        }
        if isinstance(selected_variant, dict)
        else None,
        "rank_evidence": hit.get("rank_evidence", []),
        "rank_caveats": hit.get("rank_caveats", []),
        "rank_summary": hit.get("rank_summary"),
    }


def _clamp_score(value: object) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, score))


def _clean_reason(value: object) -> str:
    if not isinstance(value, str):
        return "No reason provided."
    return " ".join(value.split())[:300] or "No reason provided."
