from __future__ import annotations

from threading import RLock

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.config import settings


_client_lock = RLock()
_qdrant_client: QdrantClient | None = None
_retrieval_service: "RetrievalService" | None = None


def get_qdrant_client() -> QdrantClient:
    global _qdrant_client

    if _qdrant_client is None:
        with _client_lock:
            if _qdrant_client is None:
                _qdrant_client = QdrantClient(path=settings.qdrant_path)

    return _qdrant_client


def get_retrieval_service() -> "RetrievalService":
    global _retrieval_service

    if _retrieval_service is None:
        with _client_lock:
            if _retrieval_service is None:
                _retrieval_service = RetrievalService()

    return _retrieval_service


class RetrievalService:
    def __init__(self) -> None:
        self.client = get_qdrant_client()
        self.collection_name = settings.qdrant_collection_name

    def recreate_collection(self, vector_size: int) -> None:
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    def upsert_points(self, points: list[PointStruct]) -> None:
        self.client.upsert(collection_name=self.collection_name, points=points)

    def search(self, vector: list[float], top_k: int) -> list[dict]:
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=top_k,
            with_payload=True,
        )
        hits = response.points
        return [
            {
                "id": str(h.id),
                "score": h.score,
                "payload": h.payload,
            }
            for h in hits
        ]
