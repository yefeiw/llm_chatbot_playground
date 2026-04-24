from __future__ import annotations

from unittest import TestCase

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Product, Variant, VariantAttribute
from app.services.product_context_service import build_retrieval_text
from app.services.variant_selection_service import enrich_hits_with_selected_variants


class VariantSelectionServiceTest(TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = sessionmaker(bind=engine, autocommit=False, autoflush=False)()

        product = Product(
            product_uid="prod_0014",
            title="Nimbus Desk Chairs Model 0014",
            brand="Nimbus",
            category="desk_chairs",
            description="Reliable desk chairs for everyday use with balanced performance.",
            rating=4.43,
            review_count=2009,
        )
        self.db.add(product)
        self.db.flush()

        default_variant = Variant(
            variant_uid="var_0014_0",
            product_id=product.id,
            variant_name="Option 1",
            is_default=True,
        )
        selected_variant = Variant(
            variant_uid="var_0014_1",
            product_id=product.id,
            variant_name="Option 2",
            is_default=False,
        )
        self.db.add_all([default_variant, selected_variant])
        self.db.flush()

        self._add_attrs(
            default_variant.id,
            {
                "color": "Green",
                "weight_kg": "2.22",
                "material": "mesh",
                "lumbar_support": "yes",
                "max_weight_lb": "275",
            },
        )
        self._add_attrs(
            selected_variant.id,
            {
                "color": "Gray",
                "weight_kg": "1.05",
                "material": "leatherette",
                "lumbar_support": "yes",
                "max_weight_lb": "300",
            },
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_enrich_hits_selects_variant_matching_rain_and_carry_query(self) -> None:
        hits = [
            {
                "id": "15",
                "score": 0.57,
                "payload": {
                    "product_uid": "prod_0014",
                    "title": "Nimbus Desk Chairs Model 0014",
                    "brand": "Nimbus",
                    "category": "desk_chairs",
                    "description": "Reliable desk chairs for everyday use with balanced performance.",
                    "price_cents": 55200,
                    "rating": 4.43,
                    "review_count": 2009,
                    "specs": [
                        "color: Green",
                        "weight_kg: 2.22",
                        "material: mesh",
                        "color: Gray",
                        "weight_kg: 1.05",
                        "material: leatherette",
                    ],
                },
            }
        ]

        enriched = enrich_hits_with_selected_variants(
            self.db,
            hits,
            "Find lightweight desk chairs suitable for carrying in rain",
        )

        payload = enriched[0]["payload"]
        self.assertEqual(payload["selected_variant"]["variant_uid"], "var_0014_1")
        self.assertEqual(payload["selected_variant"]["variant_name"], "Option 2")
        self.assertEqual(
            payload["specs"],
            [
                "color: Gray",
                "weight_kg: 1.05",
                "material: leatherette",
                "lumbar_support: yes",
                "max_weight_lb: 300",
            ],
        )

        retrieval_text = build_retrieval_text(enriched)
        self.assertIn("Price: $552.00", retrieval_text)
        self.assertIn("Selected variant: Option 2", retrieval_text)
        self.assertIn("material: leatherette", retrieval_text)
        self.assertNotIn("material: mesh", retrieval_text)

    def test_enrich_hits_selects_stronger_laptop_variant_for_generic_recommendation(self) -> None:
        product = Product(
            product_uid="prod_0391",
            title="Pulse Laptops Model 0391",
            brand="Pulse",
            category="laptops",
            description="Reliable laptops for everyday use with balanced performance.",
            rating=4.8,
            review_count=2563,
        )
        self.db.add(product)
        self.db.flush()

        default_variant = Variant(
            variant_uid="var_0391_0",
            product_id=product.id,
            variant_name="Option 1",
            is_default=True,
        )
        stronger_variant = Variant(
            variant_uid="var_0391_1",
            product_id=product.id,
            variant_name="Option 2",
            is_default=False,
        )
        self.db.add_all([default_variant, stronger_variant])
        self.db.flush()

        self._add_attrs(
            default_variant.id,
            {
                "color": "Green",
                "weight_kg": "3.29",
                "ram_gb": "8",
                "storage_gb": "512",
                "screen_inches": "15",
            },
        )
        self._add_attrs(
            stronger_variant.id,
            {
                "color": "Gray",
                "weight_kg": "1.8",
                "ram_gb": "32",
                "storage_gb": "256",
                "screen_inches": "16",
            },
        )
        self.db.commit()

        enriched = enrich_hits_with_selected_variants(
            self.db,
            [
                {
                    "id": "392",
                    "score": 0.57,
                    "payload": {
                        "product_uid": "prod_0391",
                        "title": "Pulse Laptops Model 0391",
                        "brand": "Pulse",
                        "category": "laptops",
                        "description": "Reliable laptops for everyday use with balanced performance.",
                        "price_cents": 200000,
                        "rating": 4.8,
                        "review_count": 2563,
                        "specs": [],
                    },
                }
            ],
            "laptop recommendations",
        )

        payload = enriched[0]["payload"]
        self.assertEqual(payload["selected_variant"]["variant_uid"], "var_0391_1")
        self.assertEqual(
            payload["specs"],
            [
                "color: Gray",
                "weight_kg: 1.8",
                "ram_gb: 32",
                "storage_gb: 256",
                "screen_inches: 16",
            ],
        )

    def _add_attrs(self, variant_id: int, attrs: dict[str, str]) -> None:
        for name, value in attrs.items():
            self.db.add(VariantAttribute(variant_id=variant_id, name=name, value=value))
