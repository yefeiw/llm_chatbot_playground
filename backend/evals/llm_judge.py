from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from app.core.config import settings
from evals.graders import EvalCheck, EvalMetric


CRITERIA_WEIGHTS = {
    "intent_match": 0.25,
    "hard_constraints": 0.25,
    "ranking_quality": 0.20,
    "evidence_grounding": 0.20,
    "answer_consistency": 0.10,
}

LLM_JUDGE_SYSTEM_PROMPT = """You are an expert search-quality judge for a shopping search system.
Return only compact JSON:
{
  "criteria": {
    "intent_match": {"pass": true, "score": 1.0, "reason": "..."},
    "hard_constraints": {"pass": true, "score": 1.0, "reason": "..."},
    "ranking_quality": {"pass": true, "score": 1.0, "reason": "..."},
    "evidence_grounding": {"pass": true, "score": 1.0, "reason": "..."},
    "answer_consistency": {"pass": true, "score": 1.0, "reason": "..."}
  },
  "reason": "..."
}

Rubric and weights:
- intent_match, weight 0.25: Does the result set target the user's information need and correct product category?
- hard_constraints, weight 0.25: Are explicit constraints satisfied in the top-ranked cards, especially category, required specs, budget, and follow-up context?
- ranking_quality, weight 0.20: Are better matches ranked above partial matches? Focus most on ranks 1-5.
- evidence_grounding, weight 0.20: Are evidence, caveats, and visible specs grounded in product fields without invented facts?
- answer_consistency, weight 0.10: If an answer exists, is it consistent with the ranked cards and free of unsupported product claims? If no answer is provided, pass this criterion with score 1.0.

For each criterion:
- Set pass to true only if that criterion is substantially satisfied.
- Use score 1.0 for pass and 0.0 for fail unless the criterion is mixed; for mixed cases use 0.5.
- Keep each criterion reason short and concrete.
- Do not calculate the final weighted score. The evaluator code will calculate it from your criterion scores and the fixed weights.
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
        judged = normalize_judge_response(parse_judge_response(response.output_text))
        score = weighted_judge_score(judged)
        reason = _clean_reason(judged.get("reason"))
        criteria = judged["criteria"]
        criteria_text = ", ".join(_criterion_detail(name, criteria[name]) for name in CRITERIA_WEIGHTS)
        details = f"score={score:.4f}; minimum={min_score:.4f}; reason={reason}"
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


def normalize_judge_response(payload: dict[str, Any]) -> dict[str, Any]:
    criteria_payload = payload.get("criteria") if isinstance(payload.get("criteria"), dict) else {}
    criteria: dict[str, dict[str, Any]] = {}
    for name in CRITERIA_WEIGHTS:
        raw = criteria_payload.get(name)
        if isinstance(raw, dict):
            score = _clamp_score(raw.get("score"))
            criteria[name] = {
                "pass": bool(raw.get("pass", score >= 0.5)),
                "score": score,
                "reason": _clean_reason(raw.get("reason")),
            }
        else:
            score = _clamp_score(raw)
            criteria[name] = {
                "pass": score >= 0.5,
                "score": score,
                "reason": "Criterion missing or used legacy scalar format.",
            }

    return {
        "criteria": criteria,
        "reason": _clean_reason(payload.get("reason")),
    }


def weighted_judge_score(judged: dict[str, Any]) -> float:
    criteria = judged.get("criteria") if isinstance(judged.get("criteria"), dict) else {}
    return sum(
        CRITERIA_WEIGHTS[name] * _clamp_score((criteria.get(name) or {}).get("score"))
        for name in CRITERIA_WEIGHTS
    )


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


def _criterion_detail(name: str, criterion: dict[str, Any]) -> str:
    passed = bool(criterion.get("pass"))
    score = _clamp_score(criterion.get("score"))
    reason = _clean_reason(criterion.get("reason"))
    return f"{name}(weight={CRITERIA_WEIGHTS[name]:.2f}, pass={str(passed).lower()}, score={score:.2f}, reason={reason})"
