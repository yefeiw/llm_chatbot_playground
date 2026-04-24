from __future__ import annotations

import math
import re
from copy import deepcopy


def rerank_hits(hits: list[dict], query_text: str) -> list[dict]:
    """Rerank enriched product hits before answer generation and card display."""
    query = query_text.lower()
    budget_cents = _extract_budget_cents(query)
    scored_hits = []

    for index, hit in enumerate(hits):
        enriched_hit = deepcopy(hit)
        score, reasons = _score_hit(enriched_hit, query, budget_cents)
        enriched_hit["rerank_score"] = round(score, 4)
        enriched_hit["rerank_reasons"] = reasons
        scored_hits.append((score, -index, enriched_hit))

    scored_hits.sort(reverse=True, key=lambda item: (item[0], item[1]))
    ranked_hits = [hit for _, _, hit in scored_hits]
    for rank, hit in enumerate(ranked_hits, start=1):
        hit["rank"] = rank
    return ranked_hits


def _score_hit(hit: dict, query: str, budget_cents: int | None) -> tuple[float, list[str]]:
    payload = hit.get("payload") or {}
    reasons: list[str] = []
    score = float(hit.get("score") or 0.0) * 3.0

    rating = _as_float(payload.get("rating"))
    if rating is not None:
        score += rating * 0.55
        if rating >= 4.5:
            reasons.append(f"high rating {rating}")

    review_count = _as_float(payload.get("review_count"))
    if review_count is not None:
        score += min(math.log10(review_count + 1), 4.0) * 0.08

    price_cents = _as_int(payload.get("price_cents"))
    if budget_cents is not None and price_cents is not None:
        if price_cents <= budget_cents:
            score += 1.25
            reasons.append("within budget")
        else:
            over_ratio = (price_cents - budget_cents) / budget_cents
            score -= min(3.0, 1.5 + over_ratio * 2.0)
            reasons.append("over budget")

    attrs = _selected_attrs(payload)
    attr_blob = " ".join(f"{name} {value}".lower() for name, value in attrs.items())
    for token in _query_tokens(query):
        if len(token) >= 3 and token in attr_blob:
            score += 0.35

    score += _category_score(payload, query, reasons)
    score += _spec_quality_score(payload, query, attrs, reasons)

    return score, reasons[:4]


def _category_score(payload: dict, query: str, reasons: list[str]) -> float:
    category = str(payload.get("category") or "").replace("_", " ").lower()
    if category and category in query:
        reasons.append(f"matches {category}")
        return 1.0
    singular_category = category[:-1] if category.endswith("s") else category
    if singular_category and singular_category in query:
        reasons.append(f"matches {category}")
        return 1.0
    return 0.0


def _spec_quality_score(payload: dict, query: str, attrs: dict[str, str], reasons: list[str]) -> float:
    category = str(payload.get("category") or "")
    score = 0.0

    if category == "laptops":
        ram_gb = _as_float(attrs.get("ram_gb"))
        storage_gb = _as_float(attrs.get("storage_gb"))
        if ram_gb is not None:
            score += min(ram_gb, 32.0) / 32.0 * 0.6
            if ram_gb >= 32:
                reasons.append("32GB RAM")
        if storage_gb is not None:
            score += min(storage_gb, 1024.0) / 1024.0 * 0.35

    if any(term in query for term in {"light", "lighter", "lightweight", "carry", "portable"}):
        weight_kg = _as_float(attrs.get("weight_kg"))
        if weight_kg is not None:
            score += max(0.0, 4.0 - weight_kg) * 0.4
            reasons.append(f"{weight_kg:g} kg")

    if any(term in query for term in {"rain", "water", "waterproof", "water-resistant", "weather"}):
        if attrs.get("water_resistant") == "yes" or attrs.get("waterproof") == "yes":
            score += 2.0
            reasons.append("water protection")
        elif attrs.get("water_resistant_atm"):
            score += 1.5
            reasons.append("water resistance")
        elif attrs.get("material") == "leatherette":
            score += 0.7
            reasons.append("leatherette material")
        elif attrs.get("material") == "mesh":
            score += 0.35
            reasons.append("mesh material")

    return score


def _selected_attrs(payload: dict) -> dict[str, str]:
    selected_variant = payload.get("selected_variant")
    specs = selected_variant.get("specs") if isinstance(selected_variant, dict) else payload.get("specs", [])

    attrs: dict[str, str] = {}
    for spec in specs or []:
        if not isinstance(spec, str) or ":" not in spec:
            continue
        name, value = spec.split(":", 1)
        attrs[name.strip()] = value.strip()
    return attrs


def _extract_budget_cents(query: str) -> int | None:
    match = re.search(r"(?:under|below|less than|<=?)\s*\$?(\d+(?:\.\d{1,2})?)", query)
    if not match:
        match = re.search(r"\$(\d+(?:\.\d{1,2})?)", query)
    if not match:
        return None
    return int(float(match.group(1)) * 100)


def _query_tokens(query: str) -> set[str]:
    return {
        token.strip(".,;:!?()[]{}\"'")
        for token in query.replace("_", " ").replace("-", " ").split()
    }


def _as_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
