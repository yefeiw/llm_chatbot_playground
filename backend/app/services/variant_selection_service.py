from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Product, Variant, VariantAttribute


RAIN_TERMS = {"rain", "water", "waterproof", "water-resistant", "water_resistant", "weather"}
LIGHTWEIGHT_TERMS = {"carry", "carrying", "light", "lighter", "lightweight", "portable"}
BATTERY_TERMS = {"battery", "battery-life", "battery_life"}


def enrich_hits_with_selected_variants(db: Session, hits: list[dict], query_text: str) -> list[dict]:
    """Attach one query-appropriate variant to each product hit.

    Retrieval is product-level today, but answers and cards need to agree at the
    variant level. This keeps one selected variant in both the LLM context and
    returned product cards.
    """
    product_uids = [str(hit.get("payload", {}).get("product_uid") or "") for hit in hits]
    product_uids = [uid for uid in product_uids if uid]
    if not product_uids:
        return hits

    variants_by_product = _load_variants(db, product_uids)
    enriched_hits: list[dict] = []
    for hit in hits:
        enriched_hit = deepcopy(hit)
        payload = enriched_hit.get("payload") or {}
        product_uid = str(payload.get("product_uid") or "")
        variants = variants_by_product.get(product_uid, [])
        selected_variant = _select_variant(variants, query_text, category=str(payload.get("category") or ""))
        if selected_variant:
            payload["selected_variant"] = selected_variant
            payload["specs"] = selected_variant["specs"]
        enriched_hits.append(enriched_hit)

    return enriched_hits


def _load_variants(db: Session, product_uids: list[str]) -> dict[str, list[dict[str, Any]]]:
    rows = db.execute(
        select(
            Product.product_uid,
            Variant.id,
            Variant.variant_uid,
            Variant.variant_name,
            Variant.is_default,
            VariantAttribute.name,
            VariantAttribute.value,
        )
        .join(Variant, Variant.product_id == Product.id)
        .join(VariantAttribute, VariantAttribute.variant_id == Variant.id)
        .where(Product.product_uid.in_(product_uids))
        .order_by(Product.product_uid, Variant.id, VariantAttribute.id)
    ).all()

    variants_by_product: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    for product_uid, variant_id, variant_uid, variant_name, is_default, attr_name, attr_value in rows:
        product_variants = variants_by_product[str(product_uid)]
        if variant_id not in product_variants:
            product_variants[variant_id] = {
                "variant_uid": str(variant_uid),
                "variant_name": str(variant_name),
                "is_default": bool(is_default),
                "attrs": {},
                "specs": [],
            }

        variant = product_variants[variant_id]
        variant["attrs"][str(attr_name)] = str(attr_value)
        variant["specs"].append(f"{attr_name}: {attr_value}")

    return {
        product_uid: list(variants.values())
        for product_uid, variants in variants_by_product.items()
    }


def _select_variant(variants: list[dict[str, Any]], query_text: str, category: str) -> dict[str, Any] | None:
    if not variants:
        return None

    query = query_text.lower()
    wants_rain = any(term in query for term in RAIN_TERMS)
    wants_lightweight = any(term in query for term in LIGHTWEIGHT_TERMS)
    wants_battery = any(term in query for term in BATTERY_TERMS)
    weights = [_parse_weight_kg(variant["attrs"]) for variant in variants]
    known_weights = [weight for weight in weights if weight is not None]
    max_weight = max(known_weights) if known_weights else None

    best_variant = variants[0]
    best_score = float("-inf")
    for variant, weight in zip(variants, weights):
        score = 0.01 if variant.get("is_default") else 0.0
        attrs = variant["attrs"]
        attr_blob = " ".join(f"{name} {value}".lower() for name, value in attrs.items())

        for token in _query_tokens(query):
            if token and token in attr_blob:
                score += 1.0

        score += _explicit_spec_match_score(attrs, query)

        if wants_lightweight and max_weight is not None and weight is not None:
            score += (max_weight - weight) * 2.0

        if wants_battery:
            score += _battery_score(attrs)

        if wants_rain:
            score += _rain_score(attrs)

        score += _generic_variant_quality_score(category, attrs)

        if score > best_score:
            best_variant = variant
            best_score = score

    return {
        "variant_uid": best_variant["variant_uid"],
        "variant_name": best_variant["variant_name"],
        "is_default": best_variant["is_default"],
        "specs": list(best_variant["specs"]),
    }


def _query_tokens(query: str) -> set[str]:
    return {
        token.strip(".,;:!?()[]{}\"'")
        for token in query.replace("_", " ").replace("-", " ").split()
    }


def _parse_weight_kg(attrs: dict[str, str]) -> float | None:
    try:
        return float(attrs.get("weight_kg", ""))
    except ValueError:
        return None


def _rain_score(attrs: dict[str, str]) -> float:
    score = 0.0
    if attrs.get("water_resistant") == "yes" or attrs.get("waterproof") == "yes":
        score += 6.0
    if attrs.get("water_resistant_atm"):
        score += 4.0

    material = attrs.get("material", "").lower()
    if material == "leatherette":
        score += 2.0
    elif material == "mesh":
        score += 1.0
    elif material == "fabric":
        score -= 1.0

    return score


def _explicit_spec_match_score(attrs: dict[str, str], query: str) -> float:
    score = 0.0
    for attr_name, triggers in {
        "wireless": ("wireless",),
        "noise_canceling": ("noise canceling", "noise-canceling", "noise_canceling"),
        "waterproof": ("waterproof",),
        "water_resistant": ("water resistant", "water-resistant", "water_resistant"),
        "spinner_wheels": ("spinner wheels", "spinner-wheels", "spinner_wheels"),
        "lumbar_support": ("lumbar support", "lumbar-support", "lumbar_support"),
    }.items():
        if not any(trigger in query for trigger in triggers):
            continue
        if attrs.get(attr_name) == "yes":
            score += 6.0
        elif attrs.get(attr_name) == "no":
            score -= 4.0
    return score


def _battery_score(attrs: dict[str, str]) -> float:
    score = 0.0
    battery_hours = _parse_float(attrs.get("battery_hours"))
    battery_minutes = _parse_float(attrs.get("battery_minutes"))
    battery_days = _parse_float(attrs.get("battery_days"))
    if battery_hours is not None:
        score += min(battery_hours, 60.0) / 60.0 * 1.5
    if battery_minutes is not None:
        score += min(battery_minutes, 120.0) / 120.0 * 1.5
    if battery_days is not None:
        score += min(battery_days, 14.0) / 14.0 * 1.5
    return score


def _generic_variant_quality_score(category: str, attrs: dict[str, str]) -> float:
    """Prefer stronger variants when the user did not name exact variant specs."""
    if category == "laptops":
        score = 0.0
        ram_gb = _parse_float(attrs.get("ram_gb"))
        storage_gb = _parse_float(attrs.get("storage_gb"))
        weight_kg = _parse_weight_kg(attrs)
        if ram_gb is not None:
            score += min(ram_gb, 32.0) / 32.0 * 1.2
        if storage_gb is not None:
            score += min(storage_gb, 1024.0) / 1024.0 * 0.5
        if weight_kg is not None:
            score += max(0.0, 4.0 - weight_kg) * 0.1
        return score

    if category == "suitcases":
        score = 0.0
        if attrs.get("spinner_wheels") == "yes":
            score += 0.5
        weight_kg = _parse_weight_kg(attrs)
        if weight_kg is not None:
            score += max(0.0, 4.0 - weight_kg) * 0.1
        return score

    return 0.0


def _parse_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
