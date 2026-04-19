from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import LLMEvent, RetrievalEvent
from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse, ProductResult
from app.services.embed_service import EmbedService
from app.services.llm_service import LLMService
from app.services.memory_service import MemoryService
from app.services.retrieval_service import get_retrieval_service

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    memory = MemoryService()
    embedder = EmbedService()
    retriever = get_retrieval_service()
    llm = LLMService()

    memory.ensure_session(db, request.session_id)
    memory.add_message(db, request.session_id, "user", request.message)
    messages = memory.get_messages(db, request.session_id)

    memory_text = "\n".join(f"{m.role}: {m.content}" for m in messages)

    logger.info("Embedding query", extra={"session_id": request.session_id})
    query_vector = embedder.embed_text(request.message)

    t0 = time.perf_counter()
    hits = retriever.search(query_vector, top_k=settings.retrieval_top_k)
    retrieval_latency_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "Retrieval complete",
        extra={
            "session_id": request.session_id,
            "top_k": settings.retrieval_top_k,
            "retrieval_latency_ms": retrieval_latency_ms,
        },
    )

    retrieval_text = "\n\n".join(
        [
            f"Product {h['payload'].get('product_uid')}: {h['payload'].get('title')}\n"
            f"Brand: {h['payload'].get('brand')}\n"
            f"Category: {h['payload'].get('category')}\n"
            f"Description: {h['payload'].get('description')}\n"
            f"Rating: {h['payload'].get('rating')} ({h['payload'].get('review_count')} reviews)\n"
            f"Specs: {', '.join(h['payload'].get('specs', [])[:12])}"
            for h in hits
        ]
    )

    db.add(
        RetrievalEvent(
            session_uid=request.session_id,
            query_text=request.message,
            top_k=settings.retrieval_top_k,
            results_json=json.dumps(hits),
        )
    )
    db.commit()

    t1 = time.perf_counter()
    answer = llm.generate_answer(request.message, memory_text, retrieval_text)
    llm_latency_ms = (time.perf_counter() - t1) * 1000

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
                }
            ),
        )
    )
    db.commit()

    products = [
        ProductResult(
            product_uid=str(h["payload"].get("product_uid") or ""),
            title=str(h["payload"].get("title") or ""),
            brand=str(h["payload"].get("brand") or ""),
            category=str(h["payload"].get("category") or ""),
            description=str(h["payload"].get("description") or ""),
            price_cents=h["payload"].get("price_cents"),
            image_url=h["payload"].get("image_url"),
            product_url=h["payload"].get("product_url"),
            rating=h["payload"].get("rating"),
            review_count=h["payload"].get("review_count"),
            score=h.get("score"),
            specs=h["payload"].get("specs", []),
        )
        for h in hits
    ]

    return ChatResponse(
        session_id=request.session_id,
        answer=answer,
        products=products,
    )
