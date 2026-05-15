from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvalCheck:
    name: str
    passed: bool
    details: str


@dataclass(frozen=True)
class EvalResult:
    case_id: str
    checks: list[EvalCheck]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def passed_count(self) -> int:
        return sum(1 for check in self.checks if check.passed)


def grade_case_output(
    case: dict[str, Any],
    hits: list[dict[str, Any]],
    *,
    retrieval_query: str,
    answer: str | None = None,
) -> EvalResult:
    """Grade one eval case against ranked/enriched product hits.

    These checks intentionally focus on deterministic contracts: selected
    variants, card specs, ranking source, valid evidence, and simple answer
    shape. Subjective quality should live in hosted/model-graded evals later.
    """
    case_id = str(case.get("case_id") or "unknown")
    expect = case.get("expect") or {}
    checks: list[EvalCheck] = []

    if expected_terms := _as_list(expect.get("query_should_include")):
        checks.append(_query_contains_terms(retrieval_query, expected_terms))

    if forbidden_terms := _as_list(expect.get("query_should_not_include")):
        checks.append(_query_avoids_terms(retrieval_query, forbidden_terms))

    if required_category := expect.get("required_category"):
        top_k = int(expect.get("category_top_k") or len(hits))
        checks.append(_required_category(hits[:top_k], str(required_category), top_k))

    if required_specs := _as_dict(expect.get("required_specs")):
        min_matching_cards = int(expect.get("min_matching_cards") or 1)
        checks.append(_required_specs(hits, required_specs, min_matching_cards))

    if selected_expectations := _as_dict(expect.get("selected_variant_should_match")):
        checks.extend(_selected_variant_matches(hits, selected_expectations))

    if expect.get("card_specs_equal_selected_variant_specs"):
        checks.append(_card_specs_equal_selected_variant_specs(hits))

    if acceptable_top := _as_list(expect.get("acceptable_top_product_uids")):
        checks.append(_top_product_in(hits, acceptable_top))

    if expected_top := _as_list(expect.get("expected_top_product_uids")):
        checks.append(_top_products_match(hits, expected_top))

    if expect.get("rank_source_present"):
        checks.append(_rank_source_present(hits))

    if expect.get("evidence_is_valid"):
        checks.append(_evidence_is_valid(hits))

    if answer is not None:
        if expect.get("forbidden_answer_product_list"):
            checks.append(_answer_has_no_numbered_product_list(answer))

        if "max_answer_product_names" in expect:
            checks.append(_answer_product_name_count(answer, hits, int(expect["max_answer_product_names"])))

    if not checks:
        checks.append(EvalCheck("case_has_checks", False, "No supported expectations found."))

    return EvalResult(case_id=case_id, checks=checks)


def attrs_from_specs(specs: object) -> dict[str, str]:
    attrs: dict[str, str] = {}
    if not isinstance(specs, list):
        return attrs
    for spec in specs:
        if not isinstance(spec, str) or ":" not in spec:
            continue
        name, value = spec.split(":", 1)
        attrs[name.strip()] = value.strip()
    return attrs


def selected_attrs(hit: dict[str, Any]) -> dict[str, str]:
    payload = hit.get("payload") or {}
    selected_variant = payload.get("selected_variant")
    specs = selected_variant.get("specs") if isinstance(selected_variant, dict) else payload.get("specs", [])
    return attrs_from_specs(specs)


def allowed_evidence_options(hit: dict[str, Any]) -> set[str]:
    payload = hit.get("payload") or {}
    selected_variant = payload.get("selected_variant")
    specs = selected_variant.get("specs") if isinstance(selected_variant, dict) else payload.get("specs", [])

    options = {
        f"title: {payload.get('title')}",
        f"brand: {payload.get('brand')}",
        f"category: {payload.get('category')}",
        f"price: {_format_price(payload.get('price_cents'))}",
        f"rating: {payload.get('rating')}",
        f"review_count: {payload.get('review_count')}",
    }
    if isinstance(selected_variant, dict):
        options.add(f"selected_variant: {selected_variant.get('variant_name')}")

    options.update(str(spec) for spec in specs or [])
    return {option for option in options if option and not option.endswith(": None")}


def _query_contains_terms(retrieval_query: str, expected_terms: list[str]) -> EvalCheck:
    query = retrieval_query.lower()
    missing = [term for term in expected_terms if str(term).lower() not in query]
    return EvalCheck(
        name="rewrite_contains_required_terms",
        passed=not missing,
        details="ok" if not missing else f"missing terms: {missing}; query={retrieval_query!r}",
    )


def _query_avoids_terms(retrieval_query: str, forbidden_terms: list[str]) -> EvalCheck:
    query = retrieval_query.lower()
    present = [term for term in forbidden_terms if str(term).lower() in query]
    return EvalCheck(
        name="rewrite_avoids_forbidden_terms",
        passed=not present,
        details="ok" if not present else f"forbidden terms present: {present}; query={retrieval_query!r}",
    )


def _required_category(hits: list[dict[str, Any]], required_category: str, top_k: int) -> EvalCheck:
    categories = [str((hit.get("payload") or {}).get("category") or "") for hit in hits]
    mismatches = [category for category in categories if category != required_category]
    return EvalCheck(
        name="category_precision_at_k",
        passed=bool(hits) and not mismatches,
        details=(
            f"top_{top_k} categories={categories}"
            if mismatches or not hits
            else f"all top_{top_k} cards are {required_category}"
        ),
    )


def _required_specs(
    hits: list[dict[str, Any]],
    required_specs: dict[str, Any],
    min_matching_cards: int,
) -> EvalCheck:
    matches: list[str] = []
    for hit in hits:
        attrs = selected_attrs(hit)
        if all(str(attrs.get(name)) == str(value) for name, value in required_specs.items()):
            matches.append(str((hit.get("payload") or {}).get("product_uid") or ""))

    return EvalCheck(
        name="required_spec_recall_at_k",
        passed=len(matches) >= min_matching_cards,
        details=f"matching_cards={matches}; required={required_specs}; minimum={min_matching_cards}",
    )


def _selected_variant_matches(
    hits: list[dict[str, Any]],
    expectations: dict[str, Any],
) -> list[EvalCheck]:
    hit_by_uid = {
        str((hit.get("payload") or {}).get("product_uid") or ""): hit
        for hit in hits
    }
    checks: list[EvalCheck] = []
    for product_uid, expected_attrs in expectations.items():
        hit = hit_by_uid.get(str(product_uid))
        if hit is None:
            checks.append(
                EvalCheck(
                    name=f"selected_variant_matches_expected_attrs:{product_uid}",
                    passed=False,
                    details="product not present in ranked hits",
                )
            )
            continue

        attrs = selected_attrs(hit)
        mismatches = {
            name: {"expected": str(value), "actual": attrs.get(name)}
            for name, value in _as_dict(expected_attrs).items()
            if attrs.get(name) != str(value)
        }
        checks.append(
            EvalCheck(
                name=f"selected_variant_matches_expected_attrs:{product_uid}",
                passed=not mismatches,
                details="ok" if not mismatches else f"mismatches={mismatches}",
            )
        )
    return checks


def _card_specs_equal_selected_variant_specs(hits: list[dict[str, Any]]) -> EvalCheck:
    mismatches: list[str] = []
    for hit in hits:
        payload = hit.get("payload") or {}
        selected_variant = payload.get("selected_variant")
        if not isinstance(selected_variant, dict):
            mismatches.append(str(payload.get("product_uid") or "unknown"))
            continue
        if list(payload.get("specs") or []) != list(selected_variant.get("specs") or []):
            mismatches.append(str(payload.get("product_uid") or "unknown"))

    return EvalCheck(
        name="card_specs_equal_selected_variant_specs",
        passed=not mismatches,
        details="ok" if not mismatches else f"mismatched products={mismatches}",
    )


def _top_product_in(hits: list[dict[str, Any]], acceptable_uids: list[str]) -> EvalCheck:
    top_uid = str(((hits[0].get("payload") if hits else {}) or {}).get("product_uid") or "")
    return EvalCheck(
        name="top1_in_acceptable_set",
        passed=top_uid in {str(uid) for uid in acceptable_uids},
        details=f"top_uid={top_uid}; acceptable={acceptable_uids}",
    )


def _top_products_match(hits: list[dict[str, Any]], expected_uids: list[str]) -> EvalCheck:
    actual = [str((hit.get("payload") or {}).get("product_uid") or "") for hit in hits[: len(expected_uids)]]
    expected = [str(uid) for uid in expected_uids]
    return EvalCheck(
        name="top_products_match_expected_order",
        passed=actual == expected,
        details=f"actual={actual}; expected={expected}",
    )


def _rank_source_present(hits: list[dict[str, Any]]) -> EvalCheck:
    missing = [
        str((hit.get("payload") or {}).get("product_uid") or "")
        for hit in hits
        if not hit.get("rank_source")
    ]
    return EvalCheck(
        name="rank_source_present",
        passed=not missing,
        details="ok" if not missing else f"missing rank_source={missing}",
    )


def _evidence_is_valid(hits: list[dict[str, Any]]) -> EvalCheck:
    invalid: dict[str, list[str]] = {}
    for hit in hits:
        uid = str((hit.get("payload") or {}).get("product_uid") or "")
        allowed = allowed_evidence_options(hit)
        bad = [str(value) for value in hit.get("rank_evidence", []) if str(value) not in allowed]
        if bad:
            invalid[uid] = bad

    return EvalCheck(
        name="evidence_is_valid",
        passed=not invalid,
        details="ok" if not invalid else f"invalid_evidence={invalid}",
    )


def _answer_has_no_numbered_product_list(answer: str) -> EvalCheck:
    numbered_lines = re.findall(r"(?m)^\s*\d+[\).\s-]+", answer)
    return EvalCheck(
        name="answer_has_no_product_enumeration",
        passed=not numbered_lines,
        details="ok" if not numbered_lines else f"numbered product-list markers={len(numbered_lines)}",
    )


def _answer_product_name_count(answer: str, hits: list[dict[str, Any]], max_names: int) -> EvalCheck:
    product_names = [
        str((hit.get("payload") or {}).get("title") or "")
        for hit in hits
        if (hit.get("payload") or {}).get("title")
    ]
    mentioned = [name for name in product_names if name and name.lower() in answer.lower()]
    return EvalCheck(
        name="answer_product_name_count",
        passed=len(mentioned) <= max_names,
        details=f"mentioned={mentioned}; maximum={max_names}",
    )


def _format_price(price_cents: object) -> str:
    try:
        return f"${int(price_cents) / 100:.2f}"
    except (TypeError, ValueError):
        return "unknown"


def _as_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _as_dict(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return value
