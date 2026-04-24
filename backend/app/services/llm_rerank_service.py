from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from openai import OpenAI

from app.core.config import settings
from app.services.result_rerank_service import rerank_hits as deterministic_rerank_hits


LLM_RERANK_SYSTEM_PROMPT = """You rank shopping product candidates and choose evidence for product cards.
Return only compact JSON:
{"ranked_results":[{"product_uid":"...","evidence":["..."],"caveats":["..."],"summary":"..."}]}

Rules:
- Rank only the supplied product_uid values.
- Rank by the user request and retrieval query, prioritizing explicit requested specs.
- Evidence must be copied exactly from each candidate's evidence_options.
- Caveats must be copied exactly from each candidate's caveat_options.
- Do not invent products, specs, ratings, prices, or caveats.
- Include every candidate exactly once.
"""


class LLMRerankService:
    def __init__(self, client: OpenAI | None = None) -> None:
        self.client = client or OpenAI(api_key=settings.openai_api_key)

    def rerank(self, hits: list[dict], user_message: str, retrieval_query: str) -> list[dict]:
        candidates = [_candidate_from_hit(hit) for hit in hits]
        try:
            response = self.client.responses.create(
                model=settings.openai_chat_model,
                input=[
                    {"role": "system", "content": LLM_RERANK_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "user_message": user_message,
                                "retrieval_query": retrieval_query,
                                "candidates": candidates,
                            }
                        ),
                    },
                ],
                max_output_tokens=1600,
            )
            ranked_results = _parse_ranked_results(response.output_text)
            return _apply_llm_rank(hits, candidates, ranked_results)
        except Exception:
            return _fallback_rank(hits, retrieval_query)


def _candidate_from_hit(hit: dict) -> dict:
    payload = hit.get("payload") or {}
    selected_variant = payload.get("selected_variant")
    specs = selected_variant.get("specs") if isinstance(selected_variant, dict) else payload.get("specs", [])

    evidence_options = [
        f"title: {payload.get('title')}",
        f"brand: {payload.get('brand')}",
        f"category: {payload.get('category')}",
        f"price: {_format_price(payload.get('price_cents'))}",
        f"rating: {payload.get('rating')}",
        f"review_count: {payload.get('review_count')}",
    ]
    if isinstance(selected_variant, dict):
        evidence_options.append(f"selected_variant: {selected_variant.get('variant_name')}")

    evidence_options.extend(str(spec) for spec in specs or [])
    evidence_options = [option for option in evidence_options if option and not option.endswith(": None")]

    attrs = _attrs_from_specs(specs)
    caveat_options = _caveat_options(attrs)

    return {
        "product_uid": payload.get("product_uid"),
        "title": payload.get("title"),
        "evidence_options": evidence_options,
        "caveat_options": caveat_options,
    }


def _parse_ranked_results(text: str) -> list[dict]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = [line for line in cleaned.splitlines() if not line.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    if not cleaned.startswith("{"):
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in LLM rerank response")
        cleaned = match.group(0)

    payload = json.loads(cleaned)
    ranked_results = payload.get("ranked_results")
    if not isinstance(ranked_results, list):
        raise ValueError("LLM rerank response missing ranked_results")
    return ranked_results


def _apply_llm_rank(hits: list[dict], candidates: list[dict], ranked_results: list[dict]) -> list[dict]:
    hit_by_uid = {
        str((hit.get("payload") or {}).get("product_uid")): deepcopy(hit)
        for hit in hits
    }
    candidate_by_uid = {str(candidate.get("product_uid")): candidate for candidate in candidates}
    seen: set[str] = set()
    ranked_hits: list[dict] = []

    for ranked_result in ranked_results:
        product_uid = str(ranked_result.get("product_uid") or "")
        if product_uid in seen or product_uid not in hit_by_uid:
            continue

        candidate = candidate_by_uid[product_uid]
        hit = hit_by_uid[product_uid]
        hit["rank_source"] = "llm"
        hit["rank_evidence"] = _filter_options(ranked_result.get("evidence"), candidate["evidence_options"])
        hit["rank_caveats"] = _filter_options(ranked_result.get("caveats"), candidate["caveat_options"])
        hit["rank_summary"] = _clean_summary(ranked_result.get("summary"))
        hit["rerank_reasons"] = hit["rank_evidence"]
        ranked_hits.append(hit)
        seen.add(product_uid)

    if not ranked_hits:
        raise ValueError("LLM rerank did not return any valid candidates")

    missing_hits = [hit for hit in hits if str((hit.get("payload") or {}).get("product_uid")) not in seen]
    if missing_hits:
        ranked_hits.extend(_fallback_rank(missing_hits, ""))

    for rank, hit in enumerate(ranked_hits, start=1):
        hit["rank"] = rank
    return ranked_hits


def _fallback_rank(hits: list[dict], retrieval_query: str) -> list[dict]:
    ranked_hits = deterministic_rerank_hits(hits, retrieval_query)
    for hit in ranked_hits:
        reasons = hit.get("rerank_reasons", [])
        hit["rank_source"] = "deterministic_fallback"
        hit["rank_evidence"] = [str(reason) for reason in reasons]
        hit["rank_caveats"] = []
        hit["rank_summary"] = "Ranked by deterministic fallback."
    return ranked_hits


def _filter_options(values: object, allowed_options: list[str]) -> list[str]:
    if not isinstance(values, list):
        return []
    allowed = set(allowed_options)
    return [str(value) for value in values if str(value) in allowed][:5]


def _clean_summary(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:240]


def _attrs_from_specs(specs: object) -> dict[str, str]:
    attrs: dict[str, str] = {}
    if not isinstance(specs, list):
        return attrs
    for spec in specs:
        if not isinstance(spec, str) or ":" not in spec:
            continue
        name, value = spec.split(":", 1)
        attrs[name.strip()] = value.strip()
    return attrs


def _caveat_options(attrs: dict[str, str]) -> list[str]:
    caveats: list[str] = []
    for name in ("wireless", "noise_canceling", "waterproof", "water_resistant"):
        if attrs.get(name) == "no":
            caveats.append(f"{name}: no")
    return caveats


def _format_price(price_cents: object) -> str:
    try:
        return f"${int(price_cents) / 100:.2f}"
    except (TypeError, ValueError):
        return "unknown"
