from __future__ import annotations

import random
from dataclasses import dataclass

CATEGORIES = [
    "headphones",
    "laptops",
    "monitors",
    "keyboards",
    "mice",
    "blenders",
    "coffee_makers",
    "vacuums",
    "backpacks",
    "suitcases",
]

BRANDS = ["Nova", "Zenith", "Aster", "Vertex", "Echo", "Nimbus", "Atlas", "Pulse"]


@dataclass
class ProductSeed:
    product_uid: str
    title: str
    brand: str
    category: str
    description: str
    rating: float
    review_count: int
    variants: list[dict]


def _variant_specs(category: str) -> dict[str, str]:
    base = {
        "color": random.choice(["Black", "White", "Blue", "Gray", "Green"]),
        "weight_kg": f"{round(random.uniform(0.2, 4.0), 2)}",
    }
    category_specs = {
        "headphones": {"battery_hours": str(random.randint(15, 60)), "wireless": random.choice(["yes", "no"]), "noise_canceling": random.choice(["yes", "no"]),},
        "laptops": {"ram_gb": random.choice([8, 16, 32]), "storage_gb": random.choice([256, 512, 1024]), "screen_inches": str(random.choice([13, 14, 15, 16]))},
        "monitors": {"size_inches": str(random.choice([24, 27, 32])), "panel": random.choice(["IPS", "VA", "OLED"]), "refresh_hz": str(random.choice([60, 120, 144, 165]))},
        "keyboards": {"switch_type": random.choice(["linear", "tactile", "membrane"]), "layout": random.choice(["TKL", "Full", "75%"]), "wireless": random.choice(["yes", "no"]),},
        "mice": {"dpi": str(random.choice([1600, 3200, 6400, 12000])), "wireless": random.choice(["yes", "no"]), "buttons": str(random.randint(3, 12))},
        "blenders": {"power_w": str(random.choice([500, 700, 1000, 1200])), "capacity_l": str(round(random.uniform(1.0, 2.5), 1)), "speed_levels": str(random.randint(3, 12))},
        "coffee_makers": {"capacity_cups": str(random.choice([8, 10, 12, 14])), "programmable": random.choice(["yes", "no"]), "grinder": random.choice(["yes", "no"]),},
        "vacuums": {"type": random.choice(["stick", "upright", "robot"]), "battery_minutes": str(random.randint(25, 120)), "bagless": random.choice(["yes", "no"]),},
        "backpacks": {"capacity_l": str(random.choice([18, 22, 28, 35])), "laptop_compartment": random.choice(["yes", "no"]), "water_resistant": random.choice(["yes", "no"]),},
        "suitcases": {"capacity_l": str(random.choice([30, 45, 60, 90])), "spinner_wheels": random.choice(["yes", "no"]), "shell": random.choice(["hard", "soft"]),},
    }
    base.update({k: str(v) for k, v in category_specs[category].items()})
    return base


def generate_products(total_products: int = 1000) -> list[ProductSeed]:
    random.seed(42)
    products: list[ProductSeed] = []

    for i in range(total_products):
        category = CATEGORIES[i % len(CATEGORIES)]
        brand = random.choice(BRANDS)
        title = f"{brand} {category.replace('_', ' ').title()} Model {i:04d}"
        description = f"Reliable {category.replace('_', ' ')} for everyday use with balanced performance."
        variant_count = random.randint(1, 3)

        variants = []
        for j in range(variant_count):
            variants.append(
                {
                    "variant_uid": f"var_{i:04d}_{j}",
                    "variant_name": f"Option {j+1}",
                    "is_default": j == 0,
                    "specs": _variant_specs(category),
                }
            )

        products.append(
            ProductSeed(
                product_uid=f"prod_{i:04d}",
                title=title,
                brand=brand,
                category=category,
                description=description,
                rating=round(random.uniform(3.5, 4.9), 2),
                review_count=random.randint(20, 4000),
                variants=variants,
            )
        )

    return products
