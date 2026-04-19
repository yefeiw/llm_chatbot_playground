from __future__ import annotations

import logging

from qdrant_client.models import PointStruct
from sqlalchemy.orm import Session

from app.data.mock_catalog_generator import generate_products
from app.db.models import Product, Variant, VariantAttribute
from app.services.embed_service import EmbedService
from app.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, embed_service: EmbedService, retrieval_service: RetrievalService) -> None:
        self.embed_service = embed_service
        self.retrieval_service = retrieval_service

    def seed_and_index(self, db: Session, total_products: int = 1000) -> dict:
        logger.info("Seeding products", extra={"total_products": total_products})
        db.query(VariantAttribute).delete()
        db.query(Variant).delete()
        db.query(Product).delete()
        db.commit()

        products = generate_products(total_products=total_products)
        points: list[PointStruct] = []
        vector_size = None

        for idx, item in enumerate(products):
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

            specs_lines = []
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
                    db.add(VariantAttribute(variant_id=variant.id, name=spec_name, value=spec_value))
                    specs_lines.append(f"{spec_name}: {spec_value}")

            embed_text = (
                f"Product: {item.title}\n"
                f"Brand: {item.brand}\n"
                f"Category: {item.category}\n"
                f"Description: {item.description}\n"
                f"Price: ${item.price_cents / 100:.2f}\n"
                f"Rating: {item.rating} ({item.review_count} reviews)\n"
                f"Specs: {'; '.join(specs_lines[:20])}"
            )
            vector = self.embed_service.embed_text(embed_text)
            if vector_size is None:
                vector_size = len(vector)
                self.retrieval_service.recreate_collection(vector_size=vector_size)

            points.append(
                PointStruct(
                    id=idx + 1,
                    vector=vector,
                    payload={
                        "product_uid": item.product_uid,
                        "title": item.title,
                        "brand": item.brand,
                        "category": item.category,
                        "description": item.description,
                        "price_cents": item.price_cents,
                        "image_url": item.image_url,
                        "product_url": item.product_url,
                        "rating": item.rating,
                        "review_count": item.review_count,
                        "specs": specs_lines[:30],
                    },
                )
            )

            if len(points) >= 100:
                self.retrieval_service.upsert_points(points)
                points = []

        if points:
            self.retrieval_service.upsert_points(points)

        db.commit()
        logger.info("Seeding and indexing completed", extra={"total_products": total_products})
        return {"seeded": total_products}
