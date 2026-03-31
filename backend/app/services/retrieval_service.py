from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.config import settings


class RetrievalService:
    def __init__(self) -> None:
        self.client = QdrantClient(path=settings.qdrant_path)
        self.collection_name = settings.qdrant_collection_name

    def recreate_collection(self, vector_size: int) -> None:
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    def upsert_points(self, points: list[PointStruct]) -> None:
        self.client.upsert(collection_name=self.collection_name, points=points)

    def search(self, vector: list[float], top_k: int) -> list[dict]:
        hits = self.client.search(
            collection_name=self.collection_name,
            query_vector=vector,
            limit=top_k,
            with_payload=True,
        )
        return [
            {
                "id": str(h.id),
                "score": h.score,
                "payload": h.payload,
            }
            for h in hits
        ]
