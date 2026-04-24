from __future__ import annotations


def build_retrieval_text(hits: list[dict]) -> str:
    return "\n\n".join(
        [
            f"Rank {h.get('rank') or index}\n"
            f"Product {h['payload'].get('product_uid')}: {h['payload'].get('title')}\n"
            f"Brand: {h['payload'].get('brand')}\n"
            f"Category: {h['payload'].get('category')}\n"
            f"Price: {_format_price(h['payload'].get('price_cents'))}\n"
            f"Description: {h['payload'].get('description')}\n"
            f"Rating: {h['payload'].get('rating')} ({h['payload'].get('review_count')} reviews)\n"
            f"Selected variant: {_format_selected_variant(h['payload'].get('selected_variant'))}\n"
            f"Card summary: {h.get('rank_summary') or 'Ranked product card'}\n"
            f"Evidence: {_format_ranking_notes(h.get('rank_evidence') or h.get('rerank_reasons'))}\n"
            f"Caveats: {_format_ranking_notes(h.get('rank_caveats'))}\n"
            f"Specs: {', '.join(h['payload'].get('specs', [])[:12])}"
            for index, h in enumerate(hits, start=1)
        ]
    )


def _format_price(price_cents: int | None) -> str:
    if price_cents is None:
        return "Unknown"
    return f"${price_cents / 100:.2f}"


def _format_selected_variant(selected_variant: object) -> str:
    if not isinstance(selected_variant, dict):
        return "Default product specs"
    variant_name = str(selected_variant.get("variant_name") or "Selected option")
    return variant_name


def _format_ranking_notes(rerank_reasons: object) -> str:
    if not isinstance(rerank_reasons, list) or not rerank_reasons:
        return "Semantic match"
    return ", ".join(str(reason) for reason in rerank_reasons[:4])
