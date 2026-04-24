from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import LLMEvent, RetrievalEvent
from app.db.session import get_db
from app.schemas.chat import (
    AgentStep,
    ChatRequest,
    ChatResponse,
    ProductResult,
    ReActChatResponse,
)
from app.services.embed_service import EmbedService
from app.services.llm_rerank_service import LLMRerankService
from app.services.llm_service import LLMService
from app.services.memory_service import MemoryService
from app.services.product_context_service import build_retrieval_text
from app.services.query_rewrite_service import QueryRewriteService
from app.services.react_agent_service import ReActShoppingAgentService
from app.services.retrieval_service import get_retrieval_service
from app.services.variant_selection_service import enrich_hits_with_selected_variants

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    """Run one grounded shopping-assistant turn.

    Retrieval uses a standalone query rewritten from the latest user message
    plus prior conversation, while answer generation keeps the user's original
    wording.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    memory = MemoryService()
    embedder = EmbedService()
    retriever = get_retrieval_service()
    query_rewriter = QueryRewriteService()
    reranker = LLMRerankService()
    llm = LLMService()

    memory.ensure_session(db, request.session_id)
    prior_messages = memory.get_messages(db, request.session_id)
    prior_memory_text = "\n".join(f"{m.role}: {m.content}" for m in prior_messages)

    memory.add_message(db, request.session_id, "user", request.message)
    messages = memory.get_messages(db, request.session_id)

    memory_text = "\n".join(f"{m.role}: {m.content}" for m in messages)

    logger.info("Rewriting retrieval query", extra={"session_id": request.session_id})
    try:
        retrieval_query = query_rewriter.rewrite(request.message, prior_memory_text)
    except Exception:
        logger.exception(
            "Query rewrite failed; falling back to original message",
            extra={"session_id": request.session_id},
        )
        retrieval_query = request.message.strip()

    # Retrieval happens before generation; the LLM can only recommend products
    # present in this context.
    logger.info(
        "Embedding retrieval query",
        extra={
            "session_id": request.session_id,
            "query_rewritten": retrieval_query != request.message.strip(),
        },
    )
    query_vector = embedder.embed_text(retrieval_query)

    t0 = time.perf_counter()
    hits = retriever.search(query_vector, top_k=settings.retrieval_top_k)
    retrieval_latency_ms = (time.perf_counter() - t0) * 1000
    hits = enrich_hits_with_selected_variants(db, hits, retrieval_query)
    hits = reranker.rerank(hits, request.message, retrieval_query)
    ranked_results = _ranked_results_for_log(hits)
    ranked_results_json = json.dumps(ranked_results)
    logger.info(
        "Retrieval complete",
        extra={
            "session_id": request.session_id,
            "top_k": settings.retrieval_top_k,
            "retrieval_query": retrieval_query,
            "reranked": True,
            "ranked_results": ranked_results,
            "retrieval_latency_ms": retrieval_latency_ms,
        },
    )
    logger.info(
        "Ranked results: %s",
        ranked_results_json,
        extra={"session_id": request.session_id},
    )

    retrieval_text = build_retrieval_text(hits)

    db.add(
        RetrievalEvent(
            session_uid=request.session_id,
            query_text=retrieval_query,
            top_k=settings.retrieval_top_k,
            results_json=json.dumps(hits),
        )
    )
    db.commit()

    t1 = time.perf_counter()
    answer = llm.generate_answer(request.message, memory_text, retrieval_text)
    llm_latency_ms = (time.perf_counter() - t1) * 1000
    logger.info(
        "Answer generated",
        extra={
            "session_id": request.session_id,
            "retrieval_query": retrieval_query,
            "ranked_results": ranked_results,
            "answer": answer,
            "llm_latency_ms": llm_latency_ms,
        },
    )
    logger.info(
        "Final answer: %s",
        answer,
        extra={"session_id": request.session_id},
    )

    memory.add_message(db, request.session_id, "assistant", answer)
    db.add(
        LLMEvent(
            session_uid=request.session_id,
            model=settings.openai_chat_model,
            latency_ms=llm_latency_ms,
            prompt_snapshot_json=json.dumps(
                {
                    "message_count": len(messages),
                    "retrieved_count": len(hits),
                    "user_message": request.message,
                    "retrieval_query": retrieval_query,
                    "query_rewritten": retrieval_query != request.message.strip(),
                    "reranked": True,
                    "ranked_results": ranked_results,
                    "answer": answer,
                }
            ),
        )
    )
    db.commit()

    # Product cards are returned as structured data so the frontend does not
    # have to scrape product details out of the assistant's prose.
    products = _products_from_hits(hits)

    return ChatResponse(
        session_id=request.session_id,
        answer=answer,
        products=products,
    )


@router.post("/react-demo", response_model=ReActChatResponse)
def react_demo_chat(request: ChatRequest, db: Session = Depends(get_db)) -> ReActChatResponse:
    """Run a demo ReAct-style shopping-assistant turn with a visible action trace."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    memory = MemoryService()
    retriever = get_retrieval_service()
    agent = ReActShoppingAgentService(retriever=retriever)

    memory.ensure_session(db, request.session_id)
    prior_messages = memory.get_messages(db, request.session_id)
    prior_memory_text = "\n".join(f"{m.role}: {m.content}" for m in prior_messages)

    memory.add_message(db, request.session_id, "user", request.message)
    messages = memory.get_messages(db, request.session_id)
    memory_text = "\n".join(f"{m.role}: {m.content}" for m in messages)

    result = agent.run(request.message, prior_memory_text, memory_text)

    db.add(
        RetrievalEvent(
            session_uid=request.session_id,
            query_text=result.retrieval_query,
            top_k=settings.retrieval_top_k,
            results_json=json.dumps(result.hits),
        )
    )
    db.commit()

    memory.add_message(db, request.session_id, "assistant", result.answer)
    db.add(
        LLMEvent(
            session_uid=request.session_id,
            model=settings.openai_chat_model,
            latency_ms=result.llm_latency_ms,
            prompt_snapshot_json=json.dumps(
                {
                    "agent_mode": "react_demo",
                    "message_count": len(messages),
                    "retrieved_count": len(result.hits),
                    "user_message": request.message,
                    "retrieval_query": result.retrieval_query,
                    "agent_steps": [step.__dict__ for step in result.steps],
                    "retrieval_latency_ms": result.retrieval_latency_ms,
                }
            ),
        )
    )
    db.commit()

    return ReActChatResponse(
        session_id=request.session_id,
        answer=result.answer,
        products=_products_from_hits(result.hits),
        retrieval_query=result.retrieval_query,
        agent_steps=[
            AgentStep(
                step=step.step,
                action=step.action,
                action_input=step.action_input,
                observation=step.observation,
            )
            for step in result.steps
        ],
    )


def _products_from_hits(hits: list[dict]) -> list[ProductResult]:
    products: list[ProductResult] = []
    for h in hits:
        selected_variant = h["payload"].get("selected_variant")
        variant_uid = selected_variant.get("variant_uid") if isinstance(selected_variant, dict) else None
        variant_name = selected_variant.get("variant_name") if isinstance(selected_variant, dict) else None
        products.append(
            ProductResult(
                rank=h.get("rank"),
                product_uid=str(h["payload"].get("product_uid") or ""),
                title=str(h["payload"].get("title") or ""),
                brand=str(h["payload"].get("brand") or ""),
                category=str(h["payload"].get("category") or ""),
                description=str(h["payload"].get("description") or ""),
                variant_uid=variant_uid,
                variant_name=variant_name,
                price_cents=h["payload"].get("price_cents"),
                image_url=h["payload"].get("image_url"),
                product_url=h["payload"].get("product_url"),
                rating=h["payload"].get("rating"),
                review_count=h["payload"].get("review_count"),
                score=h.get("score"),
                evidence=h.get("rank_evidence", []),
                caveats=h.get("rank_caveats", []),
                rank_summary=h.get("rank_summary"),
                specs=h["payload"].get("specs", []),
            )
        )
    return products


def _ranked_results_for_log(hits: list[dict]) -> list[dict]:
    ranked_results = []
    for index, hit in enumerate(hits, start=1):
        payload = hit.get("payload") or {}
        selected_variant = payload.get("selected_variant")
        ranked_results.append(
            {
                "rank": hit.get("rank") or index,
                "product_uid": payload.get("product_uid"),
                "title": payload.get("title"),
                "variant_uid": selected_variant.get("variant_uid") if isinstance(selected_variant, dict) else None,
                "variant_name": selected_variant.get("variant_name") if isinstance(selected_variant, dict) else None,
                "rerank_score": hit.get("rerank_score"),
                "rerank_reasons": hit.get("rerank_reasons", []),
                "rank_source": hit.get("rank_source"),
                "evidence": hit.get("rank_evidence", []),
                "caveats": hit.get("rank_caveats", []),
                "summary": hit.get("rank_summary"),
            }
        )
    return ranked_results
