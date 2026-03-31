from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import LLMEvent, Message, RetrievalEvent
from app.db.session import get_db
from app.services.embed_service import EmbedService
from app.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/session/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    messages = db.scalars(select(Message).where(Message.session_uid == session_id).order_by(Message.id.asc())).all()
    return {
        "session_id": session_id,
        "messages": [{"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in messages],
    }


@router.get("/retrieval")
def get_retrieval(session_id: str = Query(...), db: Session = Depends(get_db)):
    events = db.scalars(select(RetrievalEvent).where(RetrievalEvent.session_uid == session_id).order_by(RetrievalEvent.id.desc())).all()
    return [
        {
            "query_text": e.query_text,
            "top_k": e.top_k,
            "results": json.loads(e.results_json),
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


@router.get("/prompts/{session_id}")
def get_prompts(session_id: str, db: Session = Depends(get_db)):
    events = db.scalars(select(LLMEvent).where(LLMEvent.session_uid == session_id).order_by(LLMEvent.id.desc())).all()
    return [json.loads(e.prompt_snapshot_json) | {"created_at": e.created_at.isoformat()} for e in events]


@router.get("/logs/{session_id}")
def get_logs(session_id: str, db: Session = Depends(get_db)):
    llm_events = db.scalars(select(LLMEvent).where(LLMEvent.session_uid == session_id).order_by(LLMEvent.id.desc())).all()
    retrieval_events = db.scalars(select(RetrievalEvent).where(RetrievalEvent.session_uid == session_id).order_by(RetrievalEvent.id.desc())).all()
    return {
        "llm_events": [{"latency_ms": e.latency_ms, "model": e.model, "created_at": e.created_at.isoformat()} for e in llm_events],
        "retrieval_events": [{"query": e.query_text, "top_k": e.top_k, "created_at": e.created_at.isoformat()} for e in retrieval_events],
    }


@router.post("/reindex")
def reindex(db: Session = Depends(get_db)):
    from app.services.ingestion_service import IngestionService

    service = IngestionService(embed_service=EmbedService(), retrieval_service=RetrievalService())
    return service.seed_and_index(db, total_products=1000)


@router.get("/retrieve")
def debug_retrieve(query: str, top_k: int = 8):
    embedder = EmbedService()
    retriever = RetrievalService()
    vec = embedder.embed_text(query)
    return retriever.search(vec, top_k=top_k)
