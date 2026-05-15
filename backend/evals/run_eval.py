from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.data.mock_catalog_generator import ProductSeed, generate_products
from app.db.models import Base, Product, Variant, VariantAttribute
from app.services.llm_rerank_service import LLMRerankService, fallback_rank_hits
from app.services.query_rewrite_service import QueryRewriteService
from app.services.variant_selection_service import enrich_hits_with_selected_variants
from evals.graders import EvalResult, grade_case_output


DEFAULT_CASES_PATH = Path(__file__).parent / "cases" / "retrieval_ranking.jsonl"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local retrieval/ranking evals.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH, help="JSONL eval cases.")
    parser.add_argument("--total-products", type=int, default=1500, help="Deterministic mock catalog size.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON results.")
    parser.add_argument(
        "--live-query-rewrite",
        action="store_true",
        help="Call the live OpenAI query rewrite service instead of using fixture retrieval_query values.",
    )
    parser.add_argument(
        "--live-llm-rerank",
        action="store_true",
        help="Call the live OpenAI LLM reranker instead of deterministic fallback ranking.",
    )
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    products = generate_products(total_products=args.total_products)
    product_by_uid = {product.product_uid: product for product in products}

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    try:
        seed_variant_db(db, products)
        results = [
            run_case(
                case,
                db,
                products,
                product_by_uid,
                live_query_rewrite=args.live_query_rewrite,
                live_llm_rerank=args.live_llm_rerank,
            )
            for case in cases
        ]
    finally:
        db.close()

    if args.json:
        print(json.dumps(_json_summary(results), indent=2))
    else:
        print_human_summary(results)

    return 0 if all(result.passed for result in results) else 1


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
    return cases


def run_case(
    case: dict[str, Any],
    db: Session,
    products: list[ProductSeed],
    product_by_uid: dict[str, ProductSeed],
    *,
    live_query_rewrite: bool,
    live_llm_rerank: bool,
) -> EvalResult:
    case_input = case.get("input") or {}
    user_message = _latest_user_message(case)
    prior_memory_text = _prior_memory_text(case)
    retrieval_query = _retrieval_query(case, user_message, prior_memory_text, live_query_rewrite)

    candidate_uids = _candidate_uids(case, products)
    hits = [_hit_from_product(product_by_uid[uid]) for uid in candidate_uids if uid in product_by_uid]
    hits = enrich_hits_with_selected_variants(db, hits, retrieval_query)
    hits = _rank_hits(hits, user_message, retrieval_query, live_llm_rerank)

    return grade_case_output(
        case,
        hits,
        retrieval_query=retrieval_query,
        answer=case_input.get("answer"),
    )


def seed_variant_db(db: Session, products: list[ProductSeed]) -> None:
    for item in products:
        product = Product(
            product_uid=item.product_uid,
            title=item.title,
            brand=item.brand,
            category=item.category,
            description=item.description,
            rating=item.rating,
            review_count=item.review_count,
        )
        db.add(product)
        db.flush()

        for variant_item in item.variants:
            variant = Variant(
                variant_uid=variant_item["variant_uid"],
                product_id=product.id,
                variant_name=variant_item["variant_name"],
                is_default=variant_item["is_default"],
            )
            db.add(variant)
            db.flush()

            for spec_name, spec_value in variant_item["specs"].items():
                db.add(VariantAttribute(variant_id=variant.id, name=spec_name, value=str(spec_value)))
    db.commit()


def print_human_summary(results: list[EvalResult]) -> None:
    passed = sum(1 for result in results if result.passed)
    print(f"Eval results: {passed}/{len(results)} cases passed")
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"\n{status} {result.case_id} ({result.passed_count}/{len(result.checks)} checks)")
        for check in result.checks:
            check_status = "PASS" if check.passed else "FAIL"
            print(f"  {check_status} {check.name}: {check.details}")


def _json_summary(results: list[EvalResult]) -> dict[str, Any]:
    return {
        "passed": all(result.passed for result in results),
        "case_count": len(results),
        "passed_case_count": sum(1 for result in results if result.passed),
        "cases": [
            {
                "case_id": result.case_id,
                "passed": result.passed,
                "passed_checks": result.passed_count,
                "total_checks": len(result.checks),
                "checks": [check.__dict__ for check in result.checks],
            }
            for result in results
        ],
    }


def _latest_user_message(case: dict[str, Any]) -> str:
    messages = (case.get("input") or {}).get("messages") or []
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content") or "")
    return str((case.get("input") or {}).get("query") or "")


def _prior_memory_text(case: dict[str, Any]) -> str:
    messages = list((case.get("input") or {}).get("messages") or [])
    if not messages:
        return ""
    prior_messages = messages[:-1]
    return "\n".join(f"{message.get('role')}: {message.get('content')}" for message in prior_messages)


def _retrieval_query(
    case: dict[str, Any],
    user_message: str,
    prior_memory_text: str,
    live_query_rewrite: bool,
) -> str:
    fixture_query = (case.get("input") or {}).get("retrieval_query")
    if fixture_query and not live_query_rewrite:
        return str(fixture_query)
    if live_query_rewrite:
        return QueryRewriteService().rewrite(user_message, prior_memory_text)
    return user_message


def _candidate_uids(case: dict[str, Any], products: list[ProductSeed]) -> list[str]:
    case_input = case.get("input") or {}
    if candidate_uids := case_input.get("candidate_product_uids"):
        return [str(uid) for uid in candidate_uids]

    expect = case.get("expect") or {}
    category = expect.get("required_category")
    top_k = int(case_input.get("top_k") or 8)
    if category:
        return [product.product_uid for product in products if product.category == category][:top_k]

    raise ValueError(f"Case {case.get('case_id')} must define candidate_product_uids or required_category")


def _hit_from_product(product: ProductSeed) -> dict[str, Any]:
    specs_lines: list[str] = []
    for variant in product.variants:
        specs_lines.extend(f"{name}: {value}" for name, value in variant["specs"].items())

    return {
        "id": str(int(product.product_uid.removeprefix("prod_")) + 1),
        "score": 0.5,
        "payload": {
            "product_uid": product.product_uid,
            "title": product.title,
            "brand": product.brand,
            "category": product.category,
            "description": product.description,
            "price_cents": product.price_cents,
            "image_url": product.image_url,
            "product_url": product.product_url,
            "rating": product.rating,
            "review_count": product.review_count,
            "specs": specs_lines[:30],
        },
    }


def _rank_hits(
    hits: list[dict[str, Any]],
    user_message: str,
    retrieval_query: str,
    live_llm_rerank: bool,
) -> list[dict[str, Any]]:
    if live_llm_rerank:
        return LLMRerankService().rerank(hits, user_message, retrieval_query)

    return fallback_rank_hits(hits, retrieval_query)


if __name__ == "__main__":
    sys.exit(main())
